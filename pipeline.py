"""
Pipeline orchestrator — coordinates LLM, TTS, imgen and editor.
Runs in a background thread so the UI stays responsive.
"""
import os
import json
import threading
from datetime import datetime

from core.llm import generate_script
from core.tts import generate_audio
from core.imgen import generate_image
from core.editor import build_video

OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "output")
DB_PATH = os.path.join(os.path.dirname(__file__), "db", "projects.json")


def _load_db() -> list:
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_db(projects: list):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)


def get_projects() -> list:
    return _load_db()


def get_project(project_id: str) -> dict | None:
    return next((p for p in _load_db() if p["id"] == project_id), None)


def _set_status(projects: list, project: dict, status: str, log: str = None):
    project["status"] = status
    if log:
        if "log" not in project:
            project["log"] = []
        project["log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {log}")
        print(f"[pipeline:{project['id']}] {log}")
    _save_db(projects)


def _run_pipeline(project_id: str):
    projects = _load_db()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return

    topic = project["topic"]
    channel = project["channel"]

    try:
        proj_dir = os.path.join(OUTPUT_ROOT, project_id)
        img_dir = os.path.join(proj_dir, "images")
        aud_dir = os.path.join(proj_dir, "audio")
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(aud_dir, exist_ok=True)

        # Step 1 — Script
        _set_status(projects, project, "generating_script", "Generating script...")
        script = generate_script(topic, channel)
        project["script"] = script
        _set_status(projects, project, "script_ready",
                    f"Script ready: \"{script['title']}\" — {len(script['scenes'])} scenes")

        # Step 2 — TTS
        _set_status(projects, project, "generating_audio", "Generating audio narration...")
        for scene in script["scenes"]:
            sid = scene["id"]
            audio_path = os.path.join(aud_dir, f"audio_{sid}.mp3")
            generate_audio(scene["narration"], audio_path)
            _set_status(projects, project, "generating_audio",
                        f"Audio {sid}/{len(script['scenes'])} done")

        _set_status(projects, project, "audio_ready", "All audio files ready")

        # Step 3 — Images
        _set_status(projects, project, "generating_images",
                    "Generating images (CPU mode — this will take a while)...")
        for scene in script["scenes"]:
            sid = scene["id"]
            img_path = os.path.join(img_dir, f"image_{sid}.png")
            _set_status(projects, project, "generating_images",
                        f"Image {sid}/{len(script['scenes'])}: {scene['image_prompt'][:60]}...")
            generate_image(scene["image_prompt"], img_path)

        _set_status(projects, project, "images_ready", "All images ready")

        # Step 4 — Assemble
        _set_status(projects, project, "assembling", "Assembling final video...")
        video_path = os.path.join(proj_dir, "final.mp4")
        build_video(script["scenes"], aud_dir, img_dir, video_path)

        project["video_path"] = video_path
        _set_status(projects, project, "done", "Pipeline complete!")

    except Exception as e:
        project["error"] = str(e)
        _set_status(projects, project, "error", f"Error: {e}")


def create_project(topic: str, channel: str) -> str:
    project_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    project = {
        "id": project_id,
        "topic": topic,
        "channel": channel,
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "script": None,
        "video_path": None,
        "error": None,
        "log": [],
    }
    projects = _load_db()
    projects.insert(0, project)
    _save_db(projects)

    threading.Thread(target=_run_pipeline, args=(project_id,), daemon=True).start()
    return project_id


def retry_project(project_id: str) -> bool:
    """Reset a failed project and re-run the pipeline from scratch."""
    projects = _load_db()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project or project["status"] not in ("error",):
        return False

    project["status"] = "queued"
    project["error"] = None
    project["log"] = []
    project["script"] = None
    project["video_path"] = None
    _save_db(projects)

    threading.Thread(target=_run_pipeline, args=(project_id,), daemon=True).start()
    return True


def update_project(project_id: str, updates: dict):
    projects = _load_db()
    for p in projects:
        if p["id"] == project_id:
            p.update(updates)
            break
    _save_db(projects)


def delete_project(project_id: str) -> bool:
    projects = _load_db()
    new = [p for p in projects if p["id"] != project_id]
    if len(new) == len(projects):
        return False
    _save_db(new)
    return True
