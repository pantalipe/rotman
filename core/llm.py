"""
LLM module — generates video script via Ollama.
Returns structured JSON with scenes.
Includes retry logic for malformed JSON responses.
"""
import json
import os
import re
import ollama

PERSONAS_DIR = os.path.join(os.path.dirname(__file__), "..", "personas")

BASE_SYSTEM_PROMPT = """You are a creative video script writer specialized in short-form content (60-90 seconds).
Given a topic, generate a video script as a JSON object with the following structure:

{
  "title": "Video title",
  "channel": "channel name",
  "duration_estimate": "~60s",
  "scenes": [
    {
      "id": 1,
      "narration": "Text to be spoken by the narrator",
      "image_prompt": "Detailed english prompt for image generation, photorealistic style",
      "duration": 6
    }
  ]
}

Rules:
- Generate EXACTLY 6 scenes — no more, no less
- Each scene narration should be 1-2 short sentences max (under 25 words)
- image_prompt must be in English, detailed and descriptive (under 20 words)
- EVERY scene MUST have all four fields: id, narration, image_prompt, duration
- duration is in seconds per scene (between 5 and 10)
- Return ONLY the JSON object, no markdown, no explanation
- Do NOT include any text before or after the JSON
- Close ALL brackets and braces — the JSON must be complete and valid
"""

RETRY_PROMPT = """Your previous response had invalid or incomplete JSON.
Return ONLY the JSON object, nothing else.
CRITICAL REQUIREMENTS:
- Every scene object MUST have ALL four fields: id, narration, image_prompt, duration
- Do NOT omit image_prompt from any scene
- The JSON must start with { and end with }
- Close ALL arrays ] and objects }
- Use EXACTLY 6 scenes with short narration (under 25 words each)"""

# Required fields for each scene
SCENE_REQUIRED_FIELDS = {"id", "narration", "image_prompt", "duration"}


def _load_persona(channel: str) -> str:
    slug = channel.lower().replace(" ", "_")
    path = os.path.join(PERSONAS_DIR, f"persona_{slug}.txt")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read().strip()
            print(f"[llm] Persona loaded: persona_{slug}.txt")
            return content
        except Exception as e:
            print(f"[llm] Warning: could not read persona file: {e}")
    else:
        print(f"[llm] No persona file found for channel '{channel}' (looked for persona_{slug}.txt)")
    return ""


def _build_system_prompt(channel: str) -> str:
    """
    Builds the final system prompt.
    Injects only Tone + Language sections of the persona to keep the prompt compact.
    """
    persona = _load_persona(channel)
    if not persona:
        return BASE_SYSTEM_PROMPT

    tone_section = ""
    lang_section = ""
    current = None
    for line in persona.splitlines():
        if line.startswith("## Tone"):
            current = "tone"
        elif line.startswith("## Language"):
            current = "lang"
        elif line.startswith("## "):
            current = None
        if current == "tone":
            tone_section += line + "\n"
        elif current == "lang":
            lang_section += line + "\n"

    persona_summary = (tone_section + lang_section).strip()
    if not persona_summary:
        persona_summary = persona[:600]

    return (
        f"CHANNEL TONE & LANGUAGE for '{channel}':\n{persona_summary}\n\n---\n\n"
        + BASE_SYSTEM_PROMPT
    )


def _validate_scenes(scenes: list) -> list[str]:
    """
    Validates each scene has the required fields.
    Returns a list of error messages (empty if all valid).
    """
    errors = []
    for i, scene in enumerate(scenes):
        missing = SCENE_REQUIRED_FIELDS - set(scene.keys())
        if missing:
            errors.append(f"Scene {i+1} missing fields: {', '.join(sorted(missing))}")
    return errors


def _fix_scenes(scenes: list, topic: str) -> list:
    """
    Attempts to fill in missing fields in scenes rather than discarding them.
    Uses safe fallbacks so the pipeline can continue.
    """
    fixed = []
    for i, scene in enumerate(scenes):
        s = dict(scene)
        if "id" not in s:
            s["id"] = i + 1
        if "narration" not in s or not s["narration"]:
            s["narration"] = f"Continuing the explanation about {topic}."
        if "image_prompt" not in s or not s["image_prompt"]:
            # Generate a generic but usable prompt from the narration
            narration = s.get("narration", topic)
            s["image_prompt"] = f"photorealistic illustration of: {narration[:60]}"
        if "duration" not in s:
            s["duration"] = 7
        fixed.append(s)
    return fixed


def _extract_json(raw: str) -> dict:
    """
    Try multiple strategies to extract valid JSON from model output.
    Includes a repair strategy for truncated responses.
    """

    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 3: extract first { ... } block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 4: repair truncated JSON
    repaired = _repair_truncated_json(cleaned or raw)
    if repaired:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from model response:\n{raw[:300]}")


def _repair_truncated_json(raw: str) -> str | None:
    """
    Attempts to close a truncated JSON string by finding the last
    complete scene object and appending the missing closers.
    """
    text = raw.strip()
    start = text.find("{")
    if start == -1:
        return None

    text = text[start:]

    depth_brace   = 0
    depth_bracket = 0
    in_string     = False
    escape_next   = False
    last_complete_scene_end = -1

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
            if depth_brace == 1:
                last_complete_scene_end = i
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1

    if depth_brace == 0 and depth_bracket == 0:
        return None

    if last_complete_scene_end > 0:
        text = text[:last_complete_scene_end + 1]
        text = text + "\n  ]\n}"
        return text

    return None


def generate_script(topic: str, channel: str = "general", model: str = "phi3", max_retries: int = 3) -> dict:
    """
    Call Ollama to generate a structured video script.
    Loads a channel persona and validates all scene fields.
    Retries up to max_retries times on failure.
    """
    system_prompt = _build_system_prompt(channel)
    user_message  = f"Channel: {channel}\nTopic: {topic}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]

    for attempt in range(1, max_retries + 1):
        print(f"[llm] Attempt {attempt}/{max_retries}...")

        response = ollama.chat(
            model=model,
            messages=messages,
            options={
                "temperature": 0.5 if attempt == 1 else 0.2,
                "num_predict": 4096,
                "num_ctx":     8192,
            },
        )

        raw = response["message"]["content"].strip()

        try:
            result = _extract_json(raw)

            if "scenes" not in result or not isinstance(result["scenes"], list):
                raise ValueError("Missing 'scenes' array in response")
            if len(result["scenes"]) == 0:
                raise ValueError("Empty scenes array")

            # Validate fields — try to fix before failing
            errors = _validate_scenes(result["scenes"])
            if errors:
                print(f"[llm] Scene field issues: {errors} — attempting auto-fix")
                result["scenes"] = _fix_scenes(result["scenes"], topic)
                # Re-validate after fix
                errors = _validate_scenes(result["scenes"])
                if errors:
                    raise ValueError(f"Scene validation failed after fix: {errors}")

            print(f"[llm] Script generated: {len(result['scenes'])} scenes")
            return result

        except (ValueError, json.JSONDecodeError) as e:
            print(f"[llm] Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user",      "content": RETRY_PROMPT})

    raise ValueError(f"Failed to generate valid script after {max_retries} attempts")
