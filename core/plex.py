"""
plex.py — Plex Media Server integration.

Reads the user's Plex music library to enrich playlists with:
  • Starred/rated tracks  — rating ≥ 7 → 1.15× priority boost
  • Recently played       — recency-weighted → up to 1.10× boost
  • Artist genre tags     — embedded file tags → fill gaps in artist_genres_map

HOW IT WORKS
============
1. Authenticate via X-Plex-Token (from plex.tv account or from Plex header auth)
2. GET /library/sections → find Music libraries
3. GET /library/sections/{id}/all?type=10 → track list (type=10 = tracks)
4. Match to Spotify library by (artist_name_lower, title_lower)
5. Feed into _lb_top_uris multiplier same as Maloja / ListenBrainz

FINDING YOUR PLEX TOKEN
=======================
  Method 1: plex.tv account page → Settings → Authorized Devices → any device → token in URL
  Method 2: While streaming, open browser dev tools → Network → any Plex request → X-Plex-Token header
  Method 3: Settings → Troubleshooting → Download logs → search for X-Plex-Token

CONFIG (.env or Settings → Connect)
=====================================
  PLEX_URL=http://localhost:32400   # full URL to your Plex server
  PLEX_TOKEN=xxxxxxxxxxxxxxxxxxxx   # your Plex authentication token

RATE / CACHE
============
Minimal API calls. Results cached for 6h in memory.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_CLIENT_NAME    = "Vibesort"
_CLIENT_VERSION = "1.0"
_REQUEST_TIMEOUT = 15
_CACHE_TTL = 21600  # 6h

# In-memory cache: {server_url: {"ts": float, "tracks": [...], "genres": {...}}}
_session_cache: dict = {}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {
        "X-Plex-Token":   token,
        "X-Plex-Client-Identifier": "vibesort",
        "X-Plex-Product": _CLIENT_NAME,
        "X-Plex-Version": _CLIENT_VERSION,
        "Accept": "application/json",
    }


def _get_json(base_url: str, path: str, token: str, params: dict | None = None) -> dict | None:
    """GET a Plex endpoint and return parsed JSON (Plex supports Accept: application/json)."""
    qs = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{base_url.rstrip('/')}{path}{qs}"
    req = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def _get_xml(base_url: str, path: str, token: str, params: dict | None = None):
    """GET a Plex endpoint and return parsed XML root element."""
    # Some Plex endpoints only return XML reliably — use XML Accept header
    hdrs = dict(_headers(token))
    hdrs["Accept"] = "application/xml"
    qs = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{base_url.rstrip('/')}{path}{qs}"
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            return ET.fromstring(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ET.ParseError, OSError):
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def ping(base_url: str, token: str) -> dict | None:
    """
    Verify server is reachable and token is valid.

    Returns {"server": str, "version": str} on success, None on failure.
    """
    data = _get_json(base_url, "/", token)
    if data:
        ms = data.get("MediaContainer", {})
        return {
            "server":  ms.get("friendlyName", ms.get("machineIdentifier", "Plex")),
            "version": ms.get("version", "?"),
        }
    return None


def _find_music_sections(base_url: str, token: str) -> list[str]:
    """Return library section IDs of type 'artist' (music libraries)."""
    data = _get_json(base_url, "/library/sections", token)
    if not data:
        return []
    sections = data.get("MediaContainer", {}).get("Directory", []) or []
    return [s["key"] for s in sections if s.get("type") == "artist" and s.get("key")]


def get_tracks(base_url: str, token: str) -> list[dict]:
    """
    Return all tracks from Plex music libraries.

    Each item: {"artist": str, "title": str, "genre": str, "rating": float, "last_played": float}.
    Rating is raw Plex 0–10 scale; last_played is a Unix timestamp (0 if never played).
    Results are cached for 6h in memory.
    """
    cache_key = f"{base_url}:tracks"
    cached = _session_cache.get(cache_key)
    if cached and time.time() - cached.get("ts", 0) < _CACHE_TTL:
        return cached.get("tracks", [])

    sections = _find_music_sections(base_url, token)
    if not sections:
        return []

    all_tracks: list[dict] = []
    for section_id in sections:
        # type=10 = track, X=all (no container limit)
        data = _get_json(
            base_url,
            f"/library/sections/{section_id}/all",
            token,
            {"type": "10", "X-Plex-Container-Size": "5000"},
        )
        if not data:
            continue
        items = data.get("MediaContainer", {}).get("Metadata", []) or []
        for item in items:
            artist = (item.get("grandparentTitle") or item.get("originalTitle") or "").strip()
            title  = (item.get("title") or "").strip()
            if not artist or not title:
                continue
            # Genre is a list of dicts with "tag" key
            genres = item.get("Genre") or []
            genre  = genres[0]["tag"] if genres and isinstance(genres[0], dict) else ""
            all_tracks.append({
                "artist":      artist,
                "title":       title,
                "genre":       genre,
                "rating":      float(item.get("userRating") or 0),
                "last_played": float(item.get("lastViewedAt") or 0),
            })

    _session_cache[cache_key] = {"ts": time.time(), "tracks": all_tracks}
    return all_tracks


def get_artist_genres(base_url: str, token: str) -> dict[str, list[str]]:
    """
    Return {artist_name_lower: [genre, ...]} from the Plex music library.

    Uses embedded file genre tags — more precise than Spotify's artist genres
    for local / independent releases.
    """
    cache_key = f"{base_url}:genres"
    cached = _session_cache.get(cache_key)
    if cached and time.time() - cached.get("ts", 0) < _CACHE_TTL:
        return cached.get("genres", {})

    tracks = get_tracks(base_url, token)
    genres: dict[str, list[str]] = {}
    for t in tracks:
        artist = t["artist"].lower()
        genre  = t["genre"].lower().strip()
        if artist and genre and genre not in genres.get(artist, []):
            genres.setdefault(artist, []).append(genre)

    cached_entry = _session_cache.get(f"{base_url}:tracks", {})
    _session_cache[f"{base_url}:genres"] = {"ts": time.time(), "genres": genres}
    return genres


def match_to_spotify(
    plex_tracks: list[dict],
    all_spotify_tracks: list[dict],
    rating_threshold: float = 7.0,
    recency_days: int = 90,
) -> dict[str, float]:
    """
    Match Plex tracks to Spotify URIs and build boost multipliers.

    Rules:
      - userRating >= rating_threshold → 1.15× (explicit love signal)
      - played within recency_days     → 1.05–1.10× (recency signal)
      - both                           → max of the two
    """
    now = time.time()
    recency_cutoff = now - (recency_days * 86400)

    # Build lookup: (artist_lower, title_lower) → (rating, last_played)
    lookup: dict[tuple, tuple] = {}
    for t in plex_tracks:
        key = (t["artist"].lower().strip(), t["title"].lower().strip())
        if key[0] and key[1]:
            lookup[key] = (t.get("rating", 0.0), t.get("last_played", 0.0))

    result: dict[str, float] = {}
    for track in all_spotify_tracks:
        uri   = track.get("uri", "")
        title = track.get("name", "").lower().strip()
        if not uri:
            continue
        for artist in track.get("artists", []):
            key = (artist.get("name", "").lower().strip(), title)
            if key not in lookup:
                continue
            rating, last_played = lookup[key]
            boost = 1.0
            if rating >= rating_threshold:
                boost = max(boost, 1.15)
            if last_played and last_played >= recency_cutoff:
                # Linear from 1.05 (just played at cutoff) to 1.10 (played now)
                age_ratio = (last_played - recency_cutoff) / (now - recency_cutoff + 1)
                boost = max(boost, 1.05 + age_ratio * 0.05)
            if boost > 1.0:
                result[uri] = boost
            break

    return result
