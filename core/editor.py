"""
Video editor — assembles images + audio into final video using MoviePy v2.
"""
import os
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips


def build_video(scenes: list, audio_dir: str, image_dir: str, output_path: str):
    """
    scenes: list of dicts with keys: id, narration, duration
    audio_dir: folder with audio_1.mp3, audio_2.mp3 ...
    image_dir: folder with image_1.png, image_2.png ...
    output_path: final .mp4 path
    """
    clips = []

    for scene in scenes:
        sid = scene["id"]
        duration = scene.get("duration", 5)

        image_path = os.path.join(image_dir, f"image_{sid}.png")
        audio_path = os.path.join(audio_dir, f"audio_{sid}.mp3")

        if not os.path.exists(image_path):
            print(f"[editor] Missing image for scene {sid}, skipping")
            continue

        img_clip = ImageClip(image_path).with_duration(duration)

        if os.path.exists(audio_path):
            audio = AudioFileClip(audio_path)
            actual_duration = max(duration, audio.duration)
            img_clip = img_clip.with_duration(actual_duration).with_audio(audio)

        clips.append(img_clip)

    if not clips:
        raise ValueError("No clips to assemble.")

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp_audio.m4a",
        remove_temp=True,
        logger=None,
    )
    print(f"[editor] Video saved: {output_path}")
