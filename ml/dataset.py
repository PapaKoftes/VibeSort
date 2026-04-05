"""
dataset.py — Load local telemetry events for training.
"""

from __future__ import annotations

import json
import os

from core.telemetry import EVENTS_PATH


def load_events(path: str | None = None) -> list[dict]:
    """Parse JSONL events file; returns [] if missing or invalid."""
    p = path or EVENTS_PATH
    if not os.path.exists(p):
        return []
    rows: list[dict] = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows
