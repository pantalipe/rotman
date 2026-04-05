"""
Image generation module — uses HuggingFace Inference API (SDXL).
CPU fallback via diffusers if API unavailable.
"""
import os
import requests
from PIL import Image
import io

HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
HF_TOKEN = os.environ.get("HF_TOKEN", "")


def generate_image_api(prompt: str, output_path: str) -> bool:
    """
    Generate image via HuggingFace Inference API.
    Returns True on success, False on failure.
    """
    if not HF_TOKEN:
        return False

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {"width": 1024, "height": 576},  # 16:9
    }

    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=120)
        if response.status_code == 200:
            image = Image.open(io.BytesIO(response.content))
            image.save(output_path)
            return True
    except Exception as e:
        print(f"[imgen] API error: {e}")

    return False


def generate_image_cpu(prompt: str, output_path: str):
    """
    Fallback: generate image via diffusers on CPU.
    Slow (~5-10 min) but unlimited.
    """
    from diffusers import StableDiffusionPipeline
    import torch

    print(f"[imgen] CPU mode — this will take a few minutes...")
    pipe = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float32,
        safety_checker=None,
    )
    pipe = pipe.to("cpu")
    pipe.enable_attention_slicing()  # reduces RAM usage

    image = pipe(
        prompt,
        num_inference_steps=20,
        width=768,
        height=432,
    ).images[0]

    image.save(output_path)
    print(f"[imgen] Saved: {output_path}")


def generate_image(prompt: str, output_path: str):
    """
    Main entry: try API first, fallback to CPU.
    """
    success = generate_image_api(prompt, output_path)
    if not success:
        print("[imgen] API unavailable or no token — using CPU fallback")
        generate_image_cpu(prompt, output_path)
