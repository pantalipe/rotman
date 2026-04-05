"""
LLM module — generates video script via Ollama.
Returns structured JSON with scenes.
Includes retry logic for malformed JSON responses.
"""
import json
import re
import ollama


SYSTEM_PROMPT = """You are a creative video script writer specialized in short-form content (60-90 seconds).
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
    Retries up to max_retries times on JSON parse failure.
    """
    user_message = f"Channel: {channel}\nTopic: {topic}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
                # Add the bad response and a correction request to the conversation
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": RETRY_PROMPT})

    raise ValueError(f"Failed to generate valid script after {max_retries} attempts")
