"""
history_parser.py — Parse Spotify data export for full listening history.

Drop StreamingHistory_music_*.json files into data/ after requesting your
data at spotify.com/account/privacy (takes up to 30 days).
"""

import json
import os
import glob
import collections
from datetime import datetime


def load(data_dir: str = "data") -> list[dict]:
    """
    Load streaming history entries from:
      • data/StreamingHistory_music_*.json   (original drop location)
      • data/streaming_history/*.json        (Connect page upload location)
    """
    patterns = [
        os.path.join(data_dir, "StreamingHistory*.json"),
        os.path.join(data_dir, "streaming_history", "*.json"),
    ]
    files: list[str] = []
    seen: set[str] = set()
    for pat in patterns:
        for path in sorted(glob.glob(pat)):
            real = os.path.realpath(path)
            if real not in seen:
                seen.add(real)
                files.append(path)

    entries = []
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            try:
                entries.extend(json.load(f))
            except json.JSONDecodeError:
                print(f"  [warn] could not parse {path}")
    return entries


def play_counts(entries: list[dict], min_ms: int = 30_000) -> dict[str, int]:
    """Count streams per track URI, ignoring plays shorter than min_ms."""
    counts: dict[str, int] = collections.Counter()
    for e in entries:
        uri = e.get("spotify_track_uri")
        ms  = e.get("ms_played", 0)
        if uri and ms >= min_ms:
            counts[uri] += 1
    return dict(counts)


def sorted_uris(entries: list[dict]) -> list[str]:
    """Full history as URIs sorted by play count (most played first)."""
    counts = play_counts(entries)
    return sorted(counts, key=lambda u: counts[u], reverse=True)


def stats(entries: list[dict]) -> dict:
    if not entries:
        return {}
    counts = play_counts(entries)
    top = max(counts, key=counts.get) if counts else None
    dates = []
    for e in entries:
        ts = e.get("ts")
        if ts:
            try:
                dates.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
            except ValueError:
                pass
    total_ms = sum(e.get("ms_played", 0) for e in entries)
    return {
        "total_streams":    len(entries),
        "unique_tracks":    len(counts),
        "total_hours":      round(total_ms / 3_600_000, 1),
        "most_played_uri":  top,
        "most_played_plays": counts.get(top, 0) if top else 0,
        "earliest":         min(dates).strftime("%Y-%m-%d") if dates else None,
        "latest":           max(dates).strftime("%Y-%m-%d") if dates else None,
    }
