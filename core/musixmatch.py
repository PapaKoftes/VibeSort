"""
musixmatch.py — Musixmatch track genre and lyrics enrichment.

Musixmatch is the world's largest lyrics database, licensed by Apple Music,
Amazon Music, and Spotify.  Their free API tier provides:

  - track.get (by ISRC or name search) → music_genre_list per track
  - track.search → fuzzy name/artist lookup
  - Partial lyrics (30% of the song — enough for mood keyword analysis)

WHY THIS IS VALUABLE
====================
Unlike Deezer (artist-level genre only) and AudioDB (editorial mood labels),
Musixmatch provides PER-TRACK genre classification from a trusted, professional
source used by major streaming platforms.

ISRC-FIRST LOOKUP
=================
Spotify includes external_ids.isrc in every track.  Using ISRC avoids false
matches from common track/artist names (e.g. "Blinding Lights" by multiple
artists).  Name-based search is kept as a fallback.

SETUP
=====
  1. https://developer.musixmatch.com/  →  Sign up  →  Get API Key (free)
  2. Add MUSIXMATCH_API_KEY=your_key to your .env file and re-scan.
  Free tier: 2,000 API calls/day — more than enough for a library scan
  (cached after first run so subsequent scans cost 0 calls).

RATE LIMIT
==========
500ms gap between requests (~2 req/s) — well within free tier limits.

CACHE
=====
outputs/.musixmatch_cache.json — persistent.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".musixmatch_cache.json")
BASE_URL   = "https://api.musixmatch.com/ws/1.1/"
_RATE_GAP  = 0.50   # 500ms — conservative for free tier quota

# Musixmatch genre IDs to human-readable names (subset of most common).
# Used as a fallback when genre_name is empty but genre_id is present.
_GENRE_ID_MAP: dict[int, str] = {
    1:   "Pop",           2:   "Hip-Hop",       3:   "Electronic",
    4:   "R&B / Soul",    5:   "Rock",           6:   "Indie",
    7:   "Country",       8:   "Jazz",           9:   "Classical",
    10:  "Metal",         11:  "Punk",           12:  "Folk",
    13:  "Blues",         14:  "Reggae",         15:  "Latin",
    16:  "Gospel",        17:  "Dance",          18:  "Alternative",
    20:  "Soundtrack",    21:  "Soul",           22:  "Funk",
    23:  "Disco",         24:  "Techno",         25:  "House",
    26:  "Trance",        27:  "Drum and Bass",  28:  "Dubstep",
    29:  "Ambient",       30:  "World",
}

_last_request_time: float = 0.0


# ── Rate limiter ───────────────────────────────────────────────────────────────

def _rate_limit() -> None:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _RATE_GAP:
        time.sleep(_RATE_GAP - elapsed)
    _last_request_time = time.monotonic()


# ── HTTP ───────────────────────────────────────────────────────────────────────

def _call(endpoint: str, params: dict, api_key: str) -> dict | None:
    """
    Single Musixmatch API call.

    Returns:
      - response body dict on success (status_code 200)
      - {} on API-level errors (wrong key, not found, quota exceeded)
        → safe to cache as "no data"
      - None on network/timeout failures
        → don't cache, retry next scan
    """
    _rate_limit()
    p = dict(params)
    p["apikey"] = api_key
    p["format"] = "json"
    url = BASE_URL + endpoint + "?" + urllib.parse.urlencode(p)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Vibesort/1.0 (github.com/PapaKoftes/VibeSort)"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        header = data.get("message", {}).get("header", {})
        if header.get("status_code") == 200:
            return data.get("message", {}).get("body", {})
        # Non-200 API status (e.g. 401=bad key, 404=not found, 402=quota)
        return {}
    except urllib.error.HTTPError:
        return {}       # HTTP error — cache as empty, don't hammer
    except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
        return None     # Network failure — don't cache, retry


# ── Cache ──────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                d.setdefault("tracks", {})
                return d
        except Exception:
            pass
    return {"tracks": {}}


def _save_cache(cache: dict) -> None:
    try:
        from core.cache_io import atomic_write_json
        atomic_write_json(CACHE_PATH, cache)
    except Exception:
        pass


# ── Genre extraction ──────────────────────────────────────────────────────────

def _genres_from_track_body(track_body: dict) -> list[str]:
    """Extract genre name list from a Musixmatch track body dict."""
    track = track_body.get("track") or {}
    genre_list = track.get("primary_genres", {}).get("music_genre_list", [])
    if not genre_list:
        genre_list = track.get("secondary_genres", {}).get("music_genre_list", [])
    genres: list[str] = []
    for entry in genre_list:
        g = entry.get("music_genre") or {}
        name = g.get("music_genre_name", "").strip()
        if not name:
            gid = g.get("music_genre_id", 0)
            name = _GENRE_ID_MAP.get(gid, "")
        if name and name.lower() not in ("music", ""):
            genres.append(name)
    return genres


def _lyrics_snippet(track_body: dict) -> str | None:
    """Extract partial lyrics from a Musixmatch track body (free tier: 30%)."""
    snippet = track_body.get("snippet", {}).get("snippet_body", "")
    return snippet.strip() if snippet else None


# ── Track lookup ──────────────────────────────────────────────────────────────

def get_track_genres(
    api_key: str,
    artist: str = "",
    title: str = "",
    isrc: str = "",
    cache: dict | None = None,
) -> list[str]:
    """
    Fetch genre list for a track from Musixmatch.

    Prefers ISRC-based lookup (exact match) over name search (fuzzy).
    Returns list of genre name strings compatible with artist_genres_map.
    """
    key = isrc.upper() if isrc else f"{artist.lower().strip()}::{title.lower().strip()}"
    if not key:
        return []

    if cache is not None:
        entry = cache.get("tracks", {}).get(key)
        if entry is not None:
            return entry if isinstance(entry, list) else []

    genres: list[str] = []

    # ISRC lookup (preferred)
    if isrc:
        body = _call("track.get", {"track_isrc": isrc.upper()}, api_key)
        if body is None:
            return []   # network error — don't cache
        if body:
            genres = _genres_from_track_body(body)

    # Name search fallback
    if not genres and artist and title:
        body = _call(
            "track.search",
            {
                "q_artist": artist,
                "q_track":  title,
                "page_size": 1,
                "page":      1,
                "s_track_rating": "desc",
            },
            api_key,
        )
        if body is None:
            return []
        track_list = (body.get("track_list") or [])
        if track_list:
            genres = _genres_from_track_body({"track": track_list[0].get("track", {})})

    result = genres if genres else []
    if cache is not None:
        cache.setdefault("tracks", {})[key] = result
    return result


# ── Library enrichment ────────────────────────────────────────────────────────

def enrich_tracks(
    tracks: list[dict],
    api_key: str,
    max_tracks: int = 300,
    progress_fn=None,
) -> dict[str, list[str]]:
    """
    Fetch per-track genre data for a library.

    Returns {spotify_uri: [genre_str, ...]}.
    Processes most-popular tracks first (by Spotify popularity score).
    """
    cache = _load_cache()

    candidates = sorted(
        [t for t in tracks if t.get("uri")],
        key=lambda t: -t.get("popularity", 0),
    )[:max_tracks]

    result: dict[str, list[str]] = {}
    for i, track in enumerate(candidates):
        uri   = track.get("uri", "")
        if not uri:
            continue
        if i % 50 == 0 and progress_fn:
            progress_fn(f"Musixmatch {i}/{len(candidates)}")

        isrc  = (track.get("external_ids") or {}).get("isrc", "")
        artists = track.get("artists") or []
        artist  = artists[0].get("name", "") if artists and isinstance(artists[0], dict) else ""
        title   = track.get("name", "")

        genres = get_track_genres(
            api_key,
            artist=artist,
            title=title,
            isrc=isrc,
            cache=cache,
        )
        if genres:
            result[uri] = genres

    _save_cache(cache)
    return result


# ── Cache stats ───────────────────────────────────────────────────────────────

def cache_stats() -> dict:
    cache = _load_cache()
    return {"tracks_cached": len(cache.get("tracks", {}))}
