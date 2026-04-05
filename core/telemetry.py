"""
telemetry.py — Append-only local event log for ML / personalization (privacy: disk only).

Events go to outputs/events.jsonl (gitignored via outputs/*).
"""

from __future__ import annotations

import json
import os
import time
import uuid

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_PATH = os.path.join(_ROOT, "outputs", "events.jsonl")


def log_event(event: str, **fields) -> None:
    """
    Record one JSON object per line. ``event`` is required (e.g. deploy_playlist).
    """
    row = {
        "ts": time.time(),
        "event": event,
        "id": str(uuid.uuid4())[:12],
        **fields,
    }
    try:
        os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
        with open(EVENTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
