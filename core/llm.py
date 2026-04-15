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
- Generate 8 to 12 scenes
- Each scene narration should be 1-2 sentences max
- image_prompt must be in English, detailed and descriptive
- duration is in seconds per scene
- Return ONLY the JSON object, no markdown, no explanation
- Do NOT include any text before or after the JSON
"""

RETRY_PROMPT = """Your previous response had invalid JSON. Return ONLY the JSON object, nothing else.
No markdown, no code blocks, no explanation. Start directly with { and end with }."""


def _load_persona(channel: str) -> str:
    """
    Loads the persona file for the given channel name.
    Looks for personas/persona_<channel>.txt (case-insensitive, spaces→underscores).
    Returns the persona content or an empty string if not found.
    """
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
    """Builds the final system prompt, injecting persona if available."""
    persona = _load_persona(channel)
    if not persona:
        return BASE_SYSTEM_PROMPT

    return (
        "CHANNEL PERSONA — follow these instructions for tone, language and content:\n\n"
        + persona
        + "\n\n"
        + "---\n\n"
        + BASE_SYSTEM_PROMPT
    )


def _extract_json(raw: str) -> dict:
    """Try multiple strategies to extract valid JSON from model output."""

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

    raise ValueError(f"Could not extract valid JSON from model response:\n{raw[:300]}")


def generate_script(topic: str, channel: str = "general", model: str = "phi3", max_retries: int = 3) -> dict:
    """
    Call Ollama to generate a structured video script.
    Loads a channel persona from personas/persona_<channel>.txt if available.
    Retries up to max_retries times on JSON parse failure.
    """
    system_prompt = _build_system_prompt(channel)
    user_message = f"Channel: {channel}\nTopic: {topic}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for attempt in range(1, max_retries + 1):
        print(f"[llm] Attempt {attempt}/{max_retries}...")

        response = ollama.chat(
            model=model,
            messages=messages,
            options={"temperature": 0.5 if attempt == 1 else 0.2},
        )

        raw = response["message"]["content"].strip()

        try:
            result = _extract_json(raw)
            # Basic validation
            if "scenes" not in result or not isinstance(result["scenes"], list):
                raise ValueError("Missing 'scenes' array in response")
            if len(result["scenes"]) == 0:
                raise ValueError("Empty scenes array")
            print(f"[llm] Script generated: {len(result['scenes'])} scenes")
            return result

        except (ValueError, json.JSONDecodeError) as e:
            print(f"[llm] Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": RETRY_PROMPT})

    raise ValueError(f"Failed to generate valid script after {max_retries} attempts")
