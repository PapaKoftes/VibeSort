"""
deezer.py — Deezer public API artist genre enrichment (no API key required).

WHY THIS EXISTS
===============
When Spotify is in Development Mode ALL genre endpoints return either 403 or
empty arrays, and playlist_items is blocked for 3rd-party playlists.  Without
an external API the scorer has zero genre signal.

Deezer's public REST API works with zero authentication:
  GET https://api.deezer.com/search?q=artist:"name"  →  top tracks + album IDs
  GET https://api.deezer.com/album/{id}              →  genre list

The album endpoint reliably returns genres like "Rap/Hip Hop", "R&B",
"Rock", "Electronic", "Pop" etc. — these map correctly to Vibesort
MACRO_GENRES via genre.to_macro() and macro_genres.json.

HOW WE AVOID the artist endpoint
=================================
Deezer's GET /artist/{id} does NOT include genre data.  Instead we:
  1. Search artist's tracks     → get the unique album IDs they appear on
  2. Fetch up to 3 albums       → collect their genre lists
  3. Return the union           → {genre_name, ...}

This gives genre data for virtually every mainstream artist.

RATE LIMIT
==========
Conservative 150ms gap (≈6 req/sec).  Deezer's undocumented limit is ~50/5s.
First run for 300 artists (≈900 calls): ~135 seconds.  Subsequent runs: instant.

CACHE
=====
outputs/.deezer_cache.json — persistent, shared across runs.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
import collections

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".deezer_cache.json")
BASE_URL   = "https://api.deezer.com/"
_RATE_GAP  = 0.15   # 150ms between calls


# ── Rate limiter ──────────────────────────────────────────────────────────────

_last_request_time: float = 0.0


def _rate_limit() -> None:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _RATE_GAP:
        time.sleep(_RATE_GAP - elapsed)
    _last_request_time = time.monotonic()


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _get(path: str) -> dict | None:
    """
    Single Deezer API call.

    Returns:
      - parsed JSON dict on success
      - {} when Deezer returns an explicit error response
        → caller may cache as "confirmed no data"
      - None on transient network/timeout failures
        → caller should NOT cache; will retry on next scan
    """
    _rate_limit()
    url = BASE_URL + path
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Vibesort/1.0 (github.com/PapaKoftes/VibeSort)",
                # Force English genre names regardless of server IP region.
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        if "error" in data:
            return {}   # Deezer confirmed error — safe to cache
        return data
    except urllib.error.HTTPError as _he:
        # 404 = Deezer confirmed this resource doesn't exist — safe to cache as empty.
        # 429 / 403 / 5xx = transient (rate limit, server error) — do NOT cache;
        # the artist must be retried on the next scan.
        return {} if _he.code == 404 else None
    except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
        return None   # network failure — don't cache, retry next scan


# ── Cache ─────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                d.setdefault("artists", {})
                return d
        except Exception:
            pass
    return {"artists": {}}


def _save_cache(cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass


# ── Artist genre lookup ───────────────────────────────────────────────────────

def get_artist_genres(artist_name: str, cache: dict = None) -> list[str]:
    """
    Fetch genre names for a single artist from Deezer.

    Strategy (because GET /artist/{id} has no genre field):
      1. Search the artist's tracks → collect unique album IDs (up to 3)
      2. Fetch each album → read its genres list
      3. Return the union, ranked by frequency

    Returns list of raw genre name strings, e.g. ["Rap/Hip Hop", "R&B"].
    genre.to_macro() maps these to MACRO_GENRES via macro_genres.json.
    """
    key = artist_name.lower().strip()

    if cache is not None and key in cache.get("artists", {}):
        return cache["artists"][key]

    # Step 1: Search for artist's tracks.
    # None  = transient failure (429, 5xx, network) — skip caching, retry next scan.
    # {}    = 404 confirmed not found — safe to cache as empty below.
    # dict  = real data.
    q   = urllib.parse.urlencode({"q": f'artist:"{artist_name}"', "limit": 10})
    hit = _get(f"search?{q}")
    if hit is None:
        return []   # transient — don't cache

    tracks = hit.get("data") or []

    if not tracks and hit:
        # hit was real data (200 OK) but zero results — try broader search
        q2    = urllib.parse.urlencode({"q": artist_name, "limit": 10, "type": "track"})
        hit2  = _get(f"search?{q2}")
        if hit2 is None:
            return []   # transient — don't cache
        tracks = [
            t for t in (hit2.get("data") or [])
            if (t.get("artist") or {}).get("name", "").lower() == key
        ]

    # Collect unique album IDs (up to 3) from the matched tracks
    seen_albums: list[int] = []
    for t in tracks:
        album_id = (t.get("album") or {}).get("id")
        if album_id and album_id not in seen_albums:
            seen_albums.append(album_id)
        if len(seen_albums) >= 3:
            break

    # Step 2: Fetch each album and collect genre names
    genre_counts: dict[str, int] = collections.Counter()
    for album_id in seen_albums:
        album = _get(f"album/{album_id}")
        if not album:   # None (transient) or {} (404) — skip
            continue
        for g in (album.get("genres") or {}).get("data", []):
            name = g.get("name", "").strip()
            if name:
                genre_counts[name] += 1

    # Return genres sorted by how many albums agree on them
    result = [g for g, _ in genre_counts.most_common()]

    # Only cache if we got a definitive answer:
    # - we found genres (result is non-empty), OR
    # - we successfully searched and genuinely found nothing (tracks list was exhausted
    #   and albums returned no genres — real "no genre data on Deezer" for this artist).
    # If tracks is empty because hit was {} (404), we also cache — that's definitive.
    _got_real_response = bool(tracks) or (hit == {} and not tracks)
    if cache is not None and (_got_real_response or result):
        cache.setdefault("artists", {})[key] = result

    return result


# ── Library enrichment (main entry point) ─────────────────────────────────────

def enrich_artists(
    artist_freq: dict,
    existing_genres: dict = None,
    max_artists: int = 300,
    progress_fn=None,
) -> dict:
    """
    Enrich the most-frequent library artists with Deezer genre data.

    Args:
        artist_freq:     {artist_id: (name, count)} — from library scan.
        existing_genres: {artist_id: [genres]} — skip artists already enriched.
        max_artists:     Cap on artists to look up, sorted by library frequency.
        progress_fn:     Optional callable(msg: str) for UI progress updates.

    Returns:
        {artist_id: [raw_genre_str, ...]}  (only artists with ≥1 genre found)
    """
    cache    = _load_cache()
    existing = existing_genres or {}

    # Sort by frequency; skip artists that already have genre data
    top = sorted(
        [
            (aid, name, cnt)
            for aid, (name, cnt) in artist_freq.items()
            if not existing.get(aid)
        ],
        key=lambda x: -x[2],
    )[:max_artists]

    result: dict = {}
    total = len(top)

    for i, (aid, name, _) in enumerate(top):
        if progress_fn and (i % 10 == 0 or i == total - 1):
            progress_fn(f"Deezer genres  {i+1}/{total}: {name[:30]}")

        genres = get_artist_genres(name, cache=cache)
        if genres:
            result[aid] = genres

    _save_cache(cache)

    enriched = len(result)
    print(f"  Deezer genres         {enriched}/{total} artists enriched")
    return result


def cache_stats() -> dict:
    """Return info about the current cache state."""
    c = _load_cache()
    return {
        "artists_cached": len(c.get("artists", {})),
        "cache_path":     CACHE_PATH,
    }
