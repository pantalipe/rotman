"""
TTS module — converts narration text to audio using edge-tts.
Async, no local model required, free and unlimited.
"""
import asyncio
import edge_tts

# PT-BR voices available
VOICES = {
    "pt-br-female": "pt-BR-FranciscaNeural",
    "pt-br-male": "pt-BR-AntonioNeural",
    "en-female": "en-US-JennyNeural",
    "en-male": "en-US-GuyNeural",
}


async def _synthesize(text: str, output_path: str, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def generate_audio(text: str, output_path: str, voice_key: str = "pt-br-female"):
    """
    Generate audio file from text using edge-tts.
    Saves to output_path (.mp3).
    """
    voice = VOICES.get(voice_key, VOICES["pt-br-female"])
    asyncio.run(_synthesize(text, output_path, voice))
