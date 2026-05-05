"""
conduler_bridge.py — rotman → conduler handoff

After a video finishes rendering, notifies conduler to schedule it for
publishing. Non-fatal: if conduler is unreachable the pipeline still
completes successfully — a warning is logged and the video stays on disk.

Configuration (all optional, via environment variables):

    CONDULER_URL            Base URL of the conduler server.
                            Default: http://127.0.0.1:7071

    CONDULER_DELAY_MINUTES  Minutes from pipeline completion before the job
                            is scheduled to publish. Gives time for manual
                            review. Default: 30
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib import error, request

logger = logging.getLogger(__name__)

CONDULER_URL          = os.environ.get("CONDULER_URL", "http://127.0.0.1:7071")
DEFAULT_DELAY_MINUTES = int(os.environ.get("CONDULER_DELAY_MINUTES", "30"))

# Maps channel slugs to the platforms conduler should publish to.
# Add or edit entries here as new channels or platforms are activated.
CHANNEL_PLATFORMS: dict[str, list[str]] = {
    "bitcoinfacil": ["youtube", "instagram"],
    "pandapoints":  ["youtube", "tiktok"],
}

DEFAULT_PLATFORMS = ["youtube"]


def _scheduled_at(delay_minutes: int) -> str:
    """Returns an ISO 8601 UTC timestamp `delay_minutes` from now."""
    return (datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)).isoformat()


def _build_description(script: dict) -> str:
    """
    Builds a short publishing description from the script dict.
    Uses the first scene narration as a teaser, capped at 200 characters.
    """
    scenes = script.get("scenes", [])
    if scenes:
        narration = scenes[0].get("narration", "")
        if narration:
            return narration[:200].rstrip() + ("..." if len(narration) > 200 else "")
    return script.get("title", "")


def schedule_video(
    video_path: str,
    channel: str,
    script: dict,
    delay_minutes: int = DEFAULT_DELAY_MINUTES,
) -> bool:
    """
    POSTs a scheduling job to conduler's /api/jobs endpoint.

    Args:
        video_path:     Absolute path to the finished .mp4 file.
        channel:        Channel slug (e.g. "bitcoinfacil", "pandapoints").
        script:         Script dict produced by the pipeline — must contain
                        "title" and "scenes".
        delay_minutes:  Minutes from now to schedule publishing. Defaults to
                        CONDULER_DELAY_MINUTES env var, or 30.

    Returns:
        True if conduler accepted the job, False if unreachable or error.
    """
    channel_key = channel.lower().replace("-", "").replace(" ", "")
    platforms   = CHANNEL_PLATFORMS.get(channel_key, DEFAULT_PLATFORMS)
    title       = script.get("title", os.path.basename(video_path))
    description = _build_description(script)
    scheduled   = _scheduled_at(delay_minutes)

    payload = {
        "video_path":   video_path,
        "platforms":    platforms,
        "scheduled_at": scheduled,
        "title":        title,
        "description":  description,
        "tags":         [],
    }

    try:
        body = json.dumps(payload).encode()
        req  = request.Request(
            f"{CONDULER_URL}/api/jobs",
            data    = body,
            headers = {"Content-Type": "application/json"},
            method  = "POST",
        )
        with request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            job_id = result.get("id", "?")
            logger.info(
                "conduler: job %s created — channel: %s | platforms: %s | scheduled: %s",
                job_id[:8], channel, platforms, scheduled,
            )
            return True

    except error.URLError as e:
        logger.warning(
            "[conduler_bridge] conduler unreachable at %s (%s). "
            "Video is saved at: %s — schedule it manually via the conduler UI.",
            CONDULER_URL, e.reason, video_path,
        )
    except Exception as e:
        logger.warning("[conduler_bridge] unexpected error: %s", e)

    return False
