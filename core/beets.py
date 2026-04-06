"""
beets.py — beets music library manager integration.

beets (https://beets.io) is an open-source music library manager with extremely
rich, hand-curated tagging. Users who manage local libraries with beets have
high-quality genre, mood, rating, and BPM data that Spotify doesn't have.

WHAT WE READ
============
beets stores its library in a SQLite database (~/.config/beets/library.db or
custom path). We read it directly — no beets installation required on the
Vibesort machine (just access to the .db file).

Tables used:
  items   — one row per track: title, artist, album, genre, mood, bpm, rating,
             year, comments, and any custom flexible attributes
  albums  — album-level genre/mood/style tags that inherit to tracks

WHAT THIS PRODUCES
==================
  artist_genres_map entries  — from item.genre field (matched by artist name)
  track_tags entries         — from item.mood, item.genre, item.comments,
                               and custom beets fields (any field starting
                               with "mood_", "vibe_", "energy_", "tag_")

MATCHING
========
We match beets tracks to Spotify tracks by (artist_name_lower, title_lower).
No AcoustID fingerprinting needed — name matching covers most cases.

CONFIG (.env or Settings → Enrichment Sources)
===============================================
  BEETS_DB_PATH=/path/to/library.db   # absolute path to beets library.db
                                       # default: ~/.config/beets/library.db

CACHE
=====
No separate cache needed — the beets DB itself is the authoritative source.
We read it fresh each scan (DB reads are instant, typically <50ms).
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DEFAULT_DB_PATHS = [
    os.path.expanduser("~/.config/beets/library.db"),
    os.path.expanduser("~/AppData/Roaming/beets/library.db"),   # Windows
    os.path.expanduser("~/Library/Application Support/beets/library.db"),  # macOS
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_db() -> str | None:
    """Return the first existing beets DB path from defaults."""
    for p in _DEFAULT_DB_PATHS:
        if os.path.exists(p):
            return p
    return None


def _open_db(db_path: str) -> sqlite3.Connection | None:
    try:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        return None


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


# ── Public API ────────────────────────────────────────────────────────────────

def is_available(db_path: str | None = None) -> bool:
    """Return True if a beets database can be found and opened."""
    path = db_path or _find_db()
    if not path or not os.path.exists(path):
        return False
    conn = _open_db(path)
    if conn is None:
        return False
    conn.close()
    return True


def read_library(
    db_path: str | None = None,
) -> tuple[dict[str, list[str]], dict[str, dict[str, float]]]:
    """
    Read genres and tags from the beets library database.

    Returns:
      artist_tags  — {artist_name_lower: [genre_string, ...]}
                     to merge into artist_genres_map (by name matching)
      track_tags   — {(artist_lower, title_lower): {tag: weight}}
                     to merge into track_tags (by name matching)
    """
    path = db_path or _find_db()
    if not path or not os.path.exists(path):
        return {}, {}

    conn = _open_db(path)
    if conn is None:
        return {}, {}

    artist_tags: dict[str, list[str]] = {}
    track_tags:  dict[tuple, dict[str, float]] = {}

    try:
        cursor = conn.cursor()

        # Get column names so we handle different beets schema versions
        cursor.execute("PRAGMA table_info(items)")
        item_cols = {row[1].lower() for row in cursor.fetchall()}

        # Build SELECT clause dynamically based on available columns
        _safe_cols = ["title", "artist", "album"]
        _opt_cols  = ["genre", "mood", "bpm", "rating", "comments", "year"]
        _flex_cols = [c for c in item_cols if c.startswith(("mood_", "vibe_", "energy_", "tag_"))]
        sel_cols   = _safe_cols + [c for c in _opt_cols if c in item_cols] + _flex_cols
        sel_sql    = ", ".join(sel_cols)

        cursor.execute(f"SELECT {sel_sql} FROM items")
        rows = cursor.fetchall()

        col_idx = {col: i for i, col in enumerate(sel_cols)}

        for row in rows:
            title  = _safe_str(row[col_idx["title"]])
            artist = _safe_str(row[col_idx["artist"]])
            if not artist or not title:
                continue

            artist_key = artist.lower()
            track_key  = (artist.lower(), title.lower())
            tags: dict[str, float] = {}

            # Genre → artist_tags
            if "genre" in col_idx:
                genre_raw = _safe_str(row[col_idx["genre"]])
                if genre_raw:
                    for g in re.split(r"[,;/|]", genre_raw):
                        g = g.strip().lower()
                        if g:
                            if artist_key not in artist_tags:
                                artist_tags[artist_key] = []
                            if g not in artist_tags[artist_key]:
                                artist_tags[artist_key].append(g)

            # Mood → tag
            if "mood" in col_idx:
                mood_raw = _safe_str(row[col_idx["mood"]])
                if mood_raw:
                    for m in re.split(r"[,;/|]", mood_raw):
                        m = m.strip().lower().replace(" ", "_")
                        if m:
                            tags[m] = 0.8

            # BPM → tempo tag
            if "bpm" in col_idx:
                try:
                    bpm = float(row[col_idx["bpm"]] or 0)
                    if bpm > 0:
                        # Rough tempo tags matching packs.json vocabulary
                        if bpm < 70:
                            tags["slow"] = 0.6
                        elif bpm < 100:
                            tags["chill"] = 0.5
                        elif bpm > 140:
                            tags["hype"] = 0.5
                except (TypeError, ValueError):
                    pass

            # Rating (0-5 or 0-100) → signal strength (not mood, just weight)
            # We don't add rating as a tag but keep it in comments for future use

            # Genre also as tag (high weight — authoritative from user curation)
            if "genre" in col_idx:
                genre_raw = _safe_str(row[col_idx["genre"]])
                if genre_raw:
                    for g in re.split(r"[,;/|]", genre_raw):
                        g = g.strip().lower().replace(" ", "_")
                        if g:
                            tags[g] = 0.9

            # Flexible beets fields (mood_*, vibe_*, etc.)
            for flex_col in _flex_cols:
                if flex_col in col_idx:
                    val = _safe_str(row[col_idx[flex_col]])
                    if val and val.lower() not in ("0", "false", "none", ""):
                        tag_name = flex_col.lower().replace(" ", "_")
                        try:
                            tags[tag_name] = min(float(val), 1.0)
                        except (TypeError, ValueError):
                            tags[tag_name] = 0.7

            if tags:
                track_tags[track_key] = tags

    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        pass
    finally:
        conn.close()

    return artist_tags, track_tags


def match_to_spotify(
    beets_track_tags: dict[tuple, dict[str, float]],
    all_tracks: list[dict],
) -> dict[str, dict[str, float]]:
    """
    Convert beets (artist_lower, title_lower) keys to Spotify URIs by
    fuzzy name matching against the Spotify track list.

    Returns {spotify_uri: {tag: weight}}.
    """
    result: dict[str, dict[str, float]] = {}
    for track in all_tracks:
        uri = track.get("uri", "")
        if not uri:
            continue
        title  = track.get("name", "").lower().strip()
        for artist in track.get("artists", []):
            key = (artist.get("name", "").lower().strip(), title)
            if key in beets_track_tags:
                result[uri] = beets_track_tags[key]
                break
    return result


# ── Import at top (needed inside read_library) ────────────────────────────────
import re
