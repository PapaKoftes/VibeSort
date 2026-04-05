"""
genius.py — Optional Genius lyrics fetch (fallback after lrclib / lyrics.ovh).

Rate: ~1000 req/hr on free tier; we sleep 0.5s between live API calls.
Cache: outputs/.genius_cache.json — successful lyrics only (errors are not cached).
"""

from __future__ import annotations

import json
import os
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".genius_cache.json")

_GENIUS_DELAY = 0.5

_cache: dict | None = None


def _cache_key(artist: str, title: str) -> str:
    return f"{artist.lower().strip()}|{title.lower().strip()}"


def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except OSError:
        pass


def fetch_lyrics(api_key: str, artist: str, title: str) -> str | None:
    """
    Return plain lyrics text or None. Never caches failures or empty results.
    """
    api_key = (api_key or "").strip()
    if not api_key or not artist or not title:
        return None

    key = _cache_key(artist, title)
    cache = _load_cache()
    if key in cache:
        hit = cache[key].get("lyrics")
        return hit if isinstance(hit, str) and hit.strip() else None

    time.sleep(_GENIUS_DELAY)
    try:
        from lyricsgenius import Genius

        genius = Genius(api_key)
        genius.verbose = False
        genius.remove_section_headers = True
        song = genius.search_song(title, artist)
        if not song or not getattr(song, "lyrics", None):
            return None
        raw = str(song.lyrics).strip()
        if not raw or len(raw) < 12:
            return None
        cache[key] = {"lyrics": raw}
        _save_cache()
        return raw
    except Exception:
        return None
