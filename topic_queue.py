"""
topic_queue.py — Topic Queue for Rotman

Manages db/queue.json — a list of topics waiting to be processed.
Each item in the queue is independent from pipeline projects.
When processed, a queue item spawns a regular pipeline project.

Queue item schema:
{
    "id":         str,        # unique id (timestamp-based)
    "topic":      str,        # video topic
    "channel":    str,        # channel slug (bitcoinfacil, pandapoints, general)
    "status":     str,        # "pending" | "processing" | "done" | "error"
    "project_id": str | None, # pipeline project id once spawned
    "added_at":   str,        # ISO datetime
    "started_at": str | None,
    "done_at":    str | None,
    "error":      str | None,
}
"""

import json
import os
from datetime import datetime

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "db", "queue.json")


# ─────────────────────────────────────────────
# I/O
# ─────────────────────────────────────────────

def _load() -> list:
    if os.path.exists(QUEUE_PATH):
        with open(QUEUE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save(items: list):
    os.makedirs(os.path.dirname(QUEUE_PATH), exist_ok=True)
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def get_queue() -> list:
    """Returns all queue items, oldest first."""
    return _load()


def get_item(item_id: str) -> dict | None:
    return next((i for i in _load() if i["id"] == item_id), None)


def add_item(topic: str, channel: str = "general") -> dict:
    """Adds a single topic to the queue. Returns the new item."""
    item_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    item = {
        "id":         item_id,
        "topic":      topic.strip(),
        "channel":    channel,
        "status":     "pending",
        "project_id": None,
        "added_at":   datetime.now().isoformat(),
        "started_at": None,
        "done_at":    None,
        "error":      None,
    }
    items = _load()
    items.append(item)
    _save(items)
    return item


def add_batch(topics: list[str], channel: str = "general") -> list[dict]:
    """Adds multiple topics at once. Returns list of created items."""
    created = []
    items   = _load()
    for topic in topics:
        topic = topic.strip()
        if not topic:
            continue
        item_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        item = {
            "id":         item_id,
            "topic":      topic,
            "channel":    channel,
            "status":     "pending",
            "project_id": None,
            "added_at":   datetime.now().isoformat(),
            "started_at": None,
            "done_at":    None,
            "error":      None,
        }
        items.append(item)
        created.append(item)
    _save(items)
    return created


def next_pending() -> dict | None:
    """Returns the oldest pending item, or None if queue is empty."""
    items = _load()
    for item in items:
        if item["status"] == "pending":
            return item
    return None


def mark_processing(item_id: str, project_id: str):
    """Marks an item as processing and links it to a pipeline project."""
    items = _load()
    for item in items:
        if item["id"] == item_id:
            item["status"]     = "processing"
            item["project_id"] = project_id
            item["started_at"] = datetime.now().isoformat()
            break
    _save(items)


def mark_done(item_id: str):
    """Marks an item as done."""
    items = _load()
    for item in items:
        if item["id"] == item_id:
            item["status"]  = "done"
            item["done_at"] = datetime.now().isoformat()
            break
    _save(items)


def mark_error(item_id: str, error: str):
    """Marks an item as errored."""
    items = _load()
    for item in items:
        if item["id"] == item_id:
            item["status"]  = "error"
            item["error"]   = error
            item["done_at"] = datetime.now().isoformat()
            break
    _save(items)


def remove_item(item_id: str) -> bool:
    """Removes an item from the queue. Returns True if found and removed."""
    items = _load()
    new   = [i for i in items if i["id"] != item_id]
    if len(new) == len(items):
        return False
    _save(new)
    return True


def clear_done() -> int:
    """Removes all done items. Returns the count removed."""
    items   = _load()
    kept    = [i for i in items if i["status"] != "done"]
    removed = len(items) - len(kept)
    _save(kept)
    return removed


def stats() -> dict:
    """Returns a summary of the queue state."""
    items = _load()
    return {
        "total":      len(items),
        "pending":    sum(1 for i in items if i["status"] == "pending"),
        "processing": sum(1 for i in items if i["status"] == "processing"),
        "done":       sum(1 for i in items if i["status"] == "done"),
        "error":      sum(1 for i in items if i["status"] == "error"),
    }
