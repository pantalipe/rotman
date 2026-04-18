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
import topic_queue as tq

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


def _get_image_prompt(scene: dict, topic: str = "") -> str:
    """
    Safely retrieves the image prompt from a scene dict.
    Falls back gracefully if the field is missing or empty.
    """
    prompt = scene.get("image_prompt") or scene.get("image") or scene.get("prompt") or ""
    if not prompt.strip():
        # Build a generic but usable prompt from the narration
        narration = scene.get("narration", topic or "abstract concept")
        prompt = f"photorealistic illustration of: {narration[:80]}"
        print(f"[pipeline] Warning: scene {scene.get('id', '?')} missing image_prompt, using fallback")
    return prompt.strip()


def _run_pipeline(project_id: str, queue_item_id: str = None):
    """
    Runs the full pipeline for a project.
    If queue_item_id is provided, updates the queue item status on completion.
    """
    projects = _load_db()
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return

    topic   = project["topic"]
    channel = project["channel"]

    try:
        proj_dir = os.path.join(OUTPUT_ROOT, project_id)
        img_dir  = os.path.join(proj_dir, "images")
        aud_dir  = os.path.join(proj_dir, "audio")
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
            sid        = scene.get("id", 0)
            narration  = scene.get("narration", "")
            audio_path = os.path.join(aud_dir, f"audio_{sid}.mp3")
            generate_audio(narration, audio_path)
            _set_status(projects, project, "generating_audio",
                        f"Audio {sid}/{len(script['scenes'])} done")

        _set_status(projects, project, "audio_ready", "All audio files ready")

        # Step 3 — Images
        _set_status(projects, project, "generating_images",
                    "Generating images (CPU mode — this will take a while)...")
        for scene in script["scenes"]:
            sid          = scene.get("id", 0)
            image_prompt = _get_image_prompt(scene, topic)
            img_path     = os.path.join(img_dir, f"image_{sid}.png")
            _set_status(projects, project, "generating_images",
                        f"Image {sid}/{len(script['scenes'])}: {image_prompt[:60]}...")
            generate_image(image_prompt, img_path)

        _set_status(projects, project, "images_ready", "All images ready")

        # Step 4 — Assemble
        _set_status(projects, project, "assembling", "Assembling final video...")
        video_path = os.path.join(proj_dir, "final.mp4")
        build_video(script["scenes"], aud_dir, img_dir, video_path)

        project["video_path"] = video_path
        _set_status(projects, project, "done", "Pipeline complete!")

        if queue_item_id:
            tq.mark_done(queue_item_id)

    except Exception as e:
        project["error"] = str(e)
        _set_status(projects, project, "error", f"Error: {e}")
        if queue_item_id:
            tq.mark_error(queue_item_id, str(e))


def create_project(topic: str, channel: str) -> str:
    project_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    project = {
        "id":         project_id,
        "topic":      topic,
        "channel":    channel,
        "status":     "queued",
        "created_at": datetime.now().isoformat(),
        "script":     None,
        "video_path": None,
        "error":      None,
        "log":        [],
    }
    projects = _load_db()
    projects.insert(0, project)
    _save_db(projects)

    threading.Thread(target=_run_pipeline, args=(project_id,), daemon=True).start()
    return project_id


def process_next_from_queue() -> dict | None:
    """
    Takes the next pending item from the queue, creates a pipeline project
    for it, and starts processing in background.
    Returns the queue item with updated status, or None if queue is empty.
    """
    item = tq.next_pending()
    if not item:
        return None

    project_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    project = {
        "id":            project_id,
        "topic":         item["topic"],
        "channel":       item["channel"],
        "status":        "queued",
        "created_at":    datetime.now().isoformat(),
        "script":        None,
        "video_path":    None,
        "error":         None,
        "log":           [f"[{datetime.now().strftime('%H:%M:%S')}] Started from queue item {item['id']}"],
        "queue_item_id": item["id"],
    }
    projects = _load_db()
    projects.insert(0, project)
    _save_db(projects)

    tq.mark_processing(item["id"], project_id)

    threading.Thread(
        target=_run_pipeline,
        args=(project_id, item["id"]),
        daemon=True,
    ).start()

    item["status"]     = "processing"
    item["project_id"] = project_id
    return item


def retry_project(project_id: str) -> bool:
    """Reset a failed project and re-run the pipeline from scratch."""
    projects = _load_db()
    project  = next((p for p in projects if p["id"] == project_id), None)
    if not project or project["status"] not in ("error",):
        return False

    queue_item_id = project.get("queue_item_id")

    project["status"]     = "queued"
    project["error"]      = None
    project["log"]        = []
    project["script"]     = None
    project["video_path"] = None
    _save_db(projects)

    threading.Thread(
        target=_run_pipeline,
        args=(project_id, queue_item_id),
        daemon=True,
    ).start()
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
