"""
rym.py — Rate Your Music (Sonemic) collection export importer.

RYM has the deepest genre taxonomy on the planet (~600 micro-genres) and
crowd-sourced ratings/descriptors for virtually every album and track.

HOW TO EXPORT FROM RYM
======================
1. Log in at rateyourmusic.com
2. Go to Profile → Export Data
3. Download "Ratings export" (ratings_YYYY-MM-DD.csv) or "Collection export"
4. Point Vibesort at the file in Settings → Enrichment Sources → RYM

CSV FORMAT (RYM ratings export)
================================
Columns vary by export version. We handle both old and new formats:

New format (2022+):
  RYM Album, First Name, Last Name, First Name localized, Last Name localized,
  Title, Release_Date, Rating, Ownership, Purchase Date, Media Type, Review

Old format:
  Artist, Title, Rating, Genre, Descriptors, ...

We extract: artist, title (album or track), genre list, descriptors.

WHAT WE PRODUCE
===============
  artist_genres_map entries  — from RYM micro-genres (fed to to_macro() for
                               macro-genre mapping — RYM genres are more precise)
  track_tags entries         — from RYM descriptors (e.g. "melancholic",
                               "atmospheric", "aggressive" — maps directly to
                               Vibesort's mood vocabulary)

MATCHING
========
Match RYM album-level data to Spotify tracks by artist_name + album_name.
Track-level matching uses artist_name + track_title.

CONFIG (.env or Settings → Enrichment Sources)
===============================================
  RYM_EXPORT_PATH=/path/to/ratings_export.csv

CACHE
=====
Parsed export is cached in memory per scan session.
"""

from __future__ import annotations

import csv
import io
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── RYM descriptor → Vibesort tag mapping ─────────────────────────────────────
# RYM descriptors are freeform but commonly used ones map to our vocabulary.
_DESCRIPTOR_TAG_MAP: dict[str, str] = {
    # Mood
    "melancholic":    "melancholic",    "melancholy":     "melancholic",
    "nostalgic":      "nostalgic",      "bittersweet":    "bittersweet",
    "aggressive":     "rage",           "angry":          "rage",
    "peaceful":       "calm",           "tranquil":       "calm",
    "uplifting":      "spiritual",      "upbeat":         "happy",
    "euphoric":       "happy",          "joyful":         "happy",
    "energetic":      "hype",           "intense":        "intense",
    "atmospheric":    "ambient",        "ethereal":       "ambient",
    "dreamy":         "ambient",        "hypnotic":       "ambient",
    "dark":           "dark",           "sinister":       "dark",
    "cold":           "dark",           "eerie":          "dark",
    "introspective":  "introspective",  "contemplative":  "introspective",
    "romantic":       "love",           "intimate":       "love",
    "sensual":        "love",
    "groovy":         "groovy",         "funky":          "groovy",
    "playful":        "vibrant",        "whimsical":      "vibrant",
    "raw":            "raw",            "lo-fi":          "raw",
    "rebellious":     "rage",
    "epic":           "hype",           "anthemic":       "hype",
    "cathartic":      "sad",            "emotional":      "sad",
    "lonely":         "sad",
    "spiritual":      "spiritual",      "devotional":     "spiritual",
    "meditative":     "introspective",
    "trippy":         "mysterious",     "psychedelic":    "mysterious",
    "mysterious":     "mysterious",
    # Energy
    "energetic":      "hype",           "lively":         "vibrant",
    "slow":           "calm",           "minimal":        "ambient",
    # Texture
    "noisy":          "intense",        "heavy":          "intense",
    "soft":           "calm",           "gentle":         "calm",
}


# ── Parser ────────────────────────────────────────────────────────────────────

def _detect_columns(header: list[str]) -> dict[str, int]:
    """Map logical column names to header indices (case-insensitive)."""
    h = [c.strip().lower() for c in header]
    mapping: dict[str, int] = {}
    for i, col in enumerate(h):
        if "artist" in col and "first" not in col and "last" not in col:
            mapping.setdefault("artist", i)
        if col in ("first name", "first_name") and "artist" not in col:
            mapping.setdefault("first_name", i)
        if col in ("last name", "last_name") and "artist" not in col:
            mapping.setdefault("last_name", i)
        if "title" in col and "album" not in col:
            mapping.setdefault("title", i)
        if "album" in col and "rym" not in col:
            mapping.setdefault("album", i)
        if "genre" in col:
            mapping.setdefault("genres", i)
        if "descriptor" in col:
            mapping.setdefault("descriptors", i)
        if "rating" in col:
            mapping.setdefault("rating", i)
    return mapping


def _parse_genres(raw: str) -> list[str]:
    """Split a RYM genre string into individual genre names."""
    if not raw:
        return []
    return [g.strip().lower() for g in re.split(r"[,;|]", raw) if g.strip()]


def _parse_descriptors(raw: str) -> list[str]:
    if not raw:
        return []
    return [d.strip().lower() for d in re.split(r"[,;|]", raw) if d.strip()]


def parse_export(
    file_path: str | None = None,
    file_content: str | None = None,
) -> tuple[dict[str, list[str]], dict[tuple, dict[str, float]]]:
    """
    Parse a RYM ratings/collection export CSV.

    Provide either file_path (str path) or file_content (raw CSV text).

    Returns:
      artist_genres  — {artist_name_lower: [genre_string, ...]}
      track_tags     — {(artist_lower, title_lower): {tag: weight}}
    """
    artist_genres: dict[str, list[str]] = {}
    track_tags:    dict[tuple, dict[str, float]] = {}

    if file_path:
        try:
            with open(file_path, encoding="utf-8-sig") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            try:
                with open(file_path, encoding="latin-1") as f:
                    content = f.read()
            except OSError:
                return {}, {}
    elif file_content:
        content = file_content
    else:
        return {}, {}

    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return {}, {}

    cols = _detect_columns(rows[0])
    if not cols:
        return {}, {}

    for row in rows[1:]:
        if not row or len(row) < 2:
            continue
        try:
            # Artist name (handle "First Last" or separate first/last columns)
            artist = ""
            if "artist" in cols:
                artist = row[cols["artist"]].strip()
            elif "first_name" in cols or "last_name" in cols:
                first = row[cols.get("first_name", 0)].strip() if "first_name" in cols else ""
                last  = row[cols.get("last_name",  0)].strip() if "last_name"  in cols else ""
                artist = f"{first} {last}".strip()
            if not artist:
                continue
            artist_key = artist.lower()

            # Title (album or track)
            title = ""
            if "title" in cols:
                title = row[cols["title"]].strip()
            elif "album" in cols:
                title = row[cols["album"]].strip()

            # Genres
            genre_raw = row[cols["genres"]].strip() if "genres" in cols and cols["genres"] < len(row) else ""
            genres = _parse_genres(genre_raw)
            if genres:
                if artist_key not in artist_genres:
                    artist_genres[artist_key] = []
                for g in genres:
                    if g not in artist_genres[artist_key]:
                        artist_genres[artist_key].append(g)

            # Descriptors → mood tags
            desc_raw = row[cols["descriptors"]].strip() if "descriptors" in cols and cols["descriptors"] < len(row) else ""
            descriptors = _parse_descriptors(desc_raw)
            if descriptors and title:
                tags: dict[str, float] = {}
                for d in descriptors:
                    mapped = _DESCRIPTOR_TAG_MAP.get(d)
                    if mapped:
                        tags[mapped] = max(tags.get(mapped, 0.0), 0.75)
                    else:
                        # Unknown descriptor — add as-is with lower weight
                        clean = d.replace(" ", "_").replace("-", "_")
                        if clean and len(clean) > 2:
                            tags[clean] = 0.4
                if tags:
                    track_tags[(artist_key, title.lower())] = tags

        except (IndexError, AttributeError):
            continue

    return artist_genres, track_tags


def match_to_spotify(
    rym_track_tags: dict[tuple, dict[str, float]],
    all_tracks: list[dict],
) -> dict[str, dict[str, float]]:
    """Convert (artist_lower, title_lower) keys to Spotify URIs."""
    result: dict[str, dict[str, float]] = {}
    for track in all_tracks:
        uri = track.get("uri", "")
        if not uri:
            continue
        title = track.get("name", "").lower().strip()
        for artist in track.get("artists", []):
            key = (artist.get("name", "").lower().strip(), title)
            if key in rym_track_tags:
                result[uri] = rym_track_tags[key]
                break
        # Also try album-level match
        album = (track.get("album") or {}).get("name", "").lower().strip()
        if uri not in result and album:
            for artist in track.get("artists", []):
                key = (artist.get("name", "").lower().strip(), album)
                if key in rym_track_tags:
                    # Album-level: lower weight (shared across all album tracks)
                    result[uri] = {k: v * 0.7 for k, v in rym_track_tags[key].items()}
                    break
    return result


def match_artists_to_spotify(
    rym_artist_genres: dict[str, list[str]],
    artist_genres_map: dict[str, list[str]],
    all_tracks: list[dict],
) -> int:
    """
    Merge RYM artist genres into artist_genres_map for artists that have no genres yet.

    Matches by lowercased artist name vs Spotify artist names from all_tracks.
    Returns count of artists updated.
    """
    # Build artist_name_lower → artist_id mapping from tracks
    name_to_id: dict[str, str] = {}
    for track in all_tracks:
        for artist in track.get("artists", []):
            aid  = artist.get("id", "")
            name = artist.get("name", "").lower().strip()
            if aid and name:
                name_to_id[name] = aid

    updated = 0
    for artist_name_lower, genres in rym_artist_genres.items():
        aid = name_to_id.get(artist_name_lower)
        if aid and not artist_genres_map.get(aid):
            artist_genres_map[aid] = genres
            updated += 1
    return updated
