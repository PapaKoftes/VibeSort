"""
apple_music.py — Apple Music Library XML import.

Parses the iTunes / Apple Music library XML export to extract:
  • Loved tracks  — heart-ed in Apple Music → 1.15× priority boost
  • Play counts   — normalised play count → up to 1.10× boost
  • Ratings       — star ratings (0–100 scale) → extra boost when ≥ 60
  • Genre tags    — per-track genre from embedded file metadata

HOW IT WORKS
============
1. User exports library XML from Apple Music → File → Library → Export Library...
2. Parse the .xml plist (standard iTunes Library XML format)
3. Match tracks to Spotify library by (artist_name_lower, title_lower)
4. Feed loved/rated/played tracks into _lb_top_uris multiplier

EXPORT PATH
===========
Default: ~/Music/Music/Music Library.xml  (macOS)
Custom:  Set APPLE_MUSIC_XML_PATH in .env or drag the file into Settings.

The XML has been iTunes-format since iTunes 4 — unchanged across versions.
Both Apple Music and iTunes produce the same format.

CONFIG (.env or Settings → Enrichment Sources)
===============================================
  APPLE_MUSIC_XML_PATH=/path/to/Music Library.xml

NO DEPENDENCIES
===============
Pure stdlib — xml.etree.ElementTree + plistlib.
"""

from __future__ import annotations

import os
import plistlib
import time

_DEFAULT_PATHS = [
    os.path.expanduser("~/Music/Music/Music Library.xml"),
    os.path.expanduser("~/Music/iTunes/iTunes Music Library.xml"),
    os.path.expanduser("~/Documents/Music Library.xml"),
]


# ── Parser ────────────────────────────────────────────────────────────────────

def _find_library(xml_path: str | None = None) -> str | None:
    """Return path to the Apple Music XML file or None if not found."""
    env_path = os.getenv("APPLE_MUSIC_XML_PATH", "").strip()
    for candidate in [xml_path, env_path] + _DEFAULT_PATHS:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def is_available(xml_path: str | None = None) -> bool:
    """Return True if an Apple Music XML file can be located."""
    return _find_library(xml_path) is not None


def parse_library(
    xml_path: str | None = None,
) -> tuple[
    dict[str, list[str]],           # artist_name_lower → [genres]
    dict[tuple, dict],               # (artist_lower, title_lower) → track_info
]:
    """
    Parse the Apple Music / iTunes Library XML.

    Returns:
      artist_genres: {artist_name_lower: [genre, ...]}
      track_info:    {(artist_lower, title_lower): {
                         "loved": bool,
                         "play_count": int,
                         "rating": int,   # 0–100 (20=1★ 40=2★ 60=3★ 80=4★ 100=5★)
                         "genre": str,
                     }}
    """
    path = _find_library(xml_path)
    if not path:
        return {}, {}

    try:
        with open(path, "rb") as fh:
            data = plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException, Exception):
        return {}, {}

    tracks_dict = data.get("Tracks", {}) or {}
    artist_genres: dict[str, list[str]] = {}
    track_info: dict[tuple, dict] = {}

    for _tid, track in tracks_dict.items():
        if not isinstance(track, dict):
            continue
        # Skip non-music (podcasts, audiobooks, movies)
        kind = (track.get("Kind") or "").lower()
        if any(k in kind for k in ("podcast", "audiobook", "video", "movie")):
            continue
        if track.get("Podcast") or track.get("Has Video"):
            continue

        artist = (track.get("Artist") or track.get("Album Artist") or "").strip()
        title  = (track.get("Name") or "").strip()
        if not artist or not title:
            continue

        genre      = (track.get("Genre") or "").strip()
        loved      = bool(track.get("Loved"))
        play_count = int(track.get("Play Count") or 0)
        rating     = int(track.get("Rating") or 0)  # 0–100, multiples of 20

        key = (artist.lower(), title.lower())
        track_info[key] = {
            "loved":      loved,
            "play_count": play_count,
            "rating":     rating,
            "genre":      genre,
        }

        # Collect artist genres
        if artist and genre:
            a_lower = artist.lower()
            g_lower = genre.lower()
            if g_lower not in artist_genres.get(a_lower, []):
                artist_genres.setdefault(a_lower, []).append(g_lower)

    return artist_genres, track_info


def match_to_spotify(
    track_info: dict[tuple, dict],
    all_spotify_tracks: list[dict],
    rating_threshold: int = 60,
    recent_play_days: int = 90,
) -> dict[str, float]:
    """
    Match Apple Music tracks to Spotify URIs and compute boost multipliers.

    Rules:
      - Loved                   → 1.15×
      - Rating ≥ rating_threshold → 1.12× (4★+)
      - High play count (top 25%) → up to 1.10×
      - All stack via max()
    """
    if not track_info:
        return {}

    max_plays = max((v["play_count"] for v in track_info.values()), default=1) or 1

    result: dict[str, float] = {}
    for track in all_spotify_tracks:
        uri   = track.get("uri", "")
        title = track.get("name", "").lower().strip()
        if not uri:
            continue
        for artist in track.get("artists", []):
            key = (artist.get("name", "").lower().strip(), title)
            if key not in track_info:
                continue
            info = track_info[key]
            boost = 1.0
            if info["loved"]:
                boost = max(boost, 1.15)
            if info["rating"] >= rating_threshold:
                boost = max(boost, 1.12)
            if info["play_count"] > 0:
                norm = info["play_count"] / max_plays
                if norm >= 0.25:  # top quartile by play count
                    boost = max(boost, 1.05 + norm * 0.05)
            if boost > 1.0:
                result[uri] = boost
            break

    return result


def library_stats(xml_path: str | None = None) -> dict:
    """Return summary stats about the Apple Music library."""
    path = _find_library(xml_path)
    if not path:
        return {"available": False}
    _, track_info = parse_library(xml_path)
    loved = sum(1 for v in track_info.values() if v["loved"])
    rated = sum(1 for v in track_info.values() if v["rating"] >= 60)
    played = sum(1 for v in track_info.values() if v["play_count"] > 0)
    return {
        "available":   True,
        "total_tracks": len(track_info),
        "loved":        loved,
        "rated_4plus":  rated,
        "played":       played,
        "xml_path":     path,
    }
