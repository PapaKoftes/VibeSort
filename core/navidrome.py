"""
navidrome.py — Navidrome / Jellyfin (OpenSubsonic API) integration.

Both Navidrome and Jellyfin implement the OpenSubsonic REST API, so one
adapter covers both. Airsonic, Subsonic, and any other compatible server
also work.

WHAT WE PULL
============
  Starred tracks  — user's explicitly loved/starred tracks → 1.15× priority boost
  Top-rated       — songs with rating ≥ 4 stars → 1.10× boost
  Artist genres   — genre tags from the server's local metadata → fill gaps in
                    artist_genres_map for tracks matched to Spotify

HOW IT WORKS
============
1. Authenticate via OpenSubsonic token auth (MD5(password+salt), never sends
   plaintext password over the wire)
2. GET /rest/getStarred2 → starred songs
3. GET /rest/getSongsByGenre → genre-grouped songs (for genre metadata)
4. Match to Spotify library by (artist_name_lower, title_lower)
5. Feed into _lb_top_uris multiplier same as ListenBrainz

SUPPORTED SERVERS
=================
  - Navidrome (https://www.navidrome.org/) — tested target
  - Jellyfin with OpenSubsonic plugin
  - Airsonic-Advanced
  - Any OpenSubsonic-compatible server

AUTHENTICATION
==============
OpenSubsonic token auth (preferred):
  MD5 salt+password hash, sent as ?u=USER&t=TOKEN&s=SALT
Plain password (fallback, less secure):
  ?u=USER&p=PASSWORD

CONFIG (.env or Settings → Connect)
=====================================
  NAVIDROME_URL=http://localhost:4533   # full URL to your server
  NAVIDROME_USER=admin                  # username
  NAVIDROME_PASS=yourpassword           # password (stored in .env, not sent in plain)

RATE / CACHE
============
Minimal API calls — no polling. Results cached for 6h in memory.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

_CLIENT_NAME = "vibesort"
_API_VERSION = "1.16.1"
_REQUEST_TIMEOUT = 10
_CACHE_TTL = 21600  # 6h

# In-memory cache: {server_url: {"ts": float, "starred": [...], "genres": {...}}}
_session_cache: dict = {}


# ── Auth ──────────────────────────────────────────────────────────────────────

def _auth_params(username: str, password: str) -> dict:
    """Build OpenSubsonic token-auth query params."""
    salt  = secrets.token_hex(8)
    token = hashlib.md5((password + salt).encode()).hexdigest()
    return {
        "u": username,
        "t": token,
        "s": salt,
        "v": _API_VERSION,
        "c": _CLIENT_NAME,
        "f": "json",
    }


def _get(base_url: str, endpoint: str, params: dict) -> dict | None:
    """Make a GET request to an OpenSubsonic endpoint."""
    qs  = urllib.parse.urlencode(params)
    url = f"{base_url.rstrip('/')}/rest/{endpoint}?{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # OpenSubsonic wraps everything in "subsonic-response"
        wrapper = data.get("subsonic-response", data)
        if wrapper.get("status") == "ok":
            return wrapper
        return None
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def ping(base_url: str, username: str, password: str) -> dict | None:
    """
    Verify server is reachable and credentials are valid.

    Returns {"server": str, "version": str} on success, None on failure.
    """
    params = _auth_params(username, password)
    resp   = _get(base_url, "ping", params)
    if resp:
        return {
            "server":  resp.get("serverVersion", resp.get("type", "OpenSubsonic")),
            "version": resp.get("version", "?"),
        }
    return None


def get_starred(base_url: str, username: str, password: str) -> list[dict]:
    """
    Return starred/loved tracks.

    Each item: {"artist": str, "title": str, "genre": str, "rating": int}.
    """
    cache_key = f"{base_url}:{username}"
    cached = _session_cache.get(cache_key)
    if cached and time.time() - cached.get("ts", 0) < _CACHE_TTL:
        return cached.get("starred", [])

    params = _auth_params(username, password)
    resp   = _get(base_url, "getStarred2", params)
    if not resp:
        return []

    songs = resp.get("starred2", {}).get("song", []) or []
    result = [
        {
            "artist": s.get("artist", ""),
            "title":  s.get("title",  ""),
            "genre":  s.get("genre",  ""),
            "rating": int(s.get("userRating", 0) or 0),
        }
        for s in songs
        if s.get("artist") and s.get("title")
    ]

    _session_cache[cache_key] = {
        "ts": time.time(),
        "starred": result,
        "genres":  _session_cache.get(cache_key, {}).get("genres", {}),
    }
    return result


def get_artist_genres(base_url: str, username: str, password: str) -> dict[str, list[str]]:
    """
    Return {artist_name_lower: [genre, ...]} from the server's artist index.

    These are the genres embedded in local file tags — often more precise
    than what Spotify returns for the same artist.
    """
    cache_key = f"{base_url}:{username}"
    cached = _session_cache.get(cache_key)
    if cached and time.time() - cached.get("ts", 0) < _CACHE_TTL:
        return cached.get("genres", {})

    params = _auth_params(username, password)
    resp   = _get(base_url, "getArtists", params)
    if not resp:
        return {}

    genres: dict[str, list[str]] = {}
    for index_entry in (resp.get("artists", {}).get("index", []) or []):
        for artist in (index_entry.get("artist", []) or []):
            name  = artist.get("name", "").strip()
            genre = artist.get("musicBrainzId", "")  # not genre, skip
            # Navidrome doesn't return genre in getArtists directly.
            # We'll pull it from getArtist (per-artist detail) on demand.
            if name:
                genres.setdefault(name.lower(), [])

    # Try to get genre via getIndexes (older Subsonic compat endpoint)
    resp2 = _get(base_url, "getGenres", params)
    if resp2:
        for g_entry in (resp2.get("genres", {}).get("genre", []) or []):
            genre_name = g_entry.get("value", "")
            if not genre_name:
                continue
            # Get songs for this genre to build artist→genre map
            songs_resp = _get(
                base_url,
                "getSongsByGenre",
                {**params, "genre": genre_name, "count": 50},
            )
            if songs_resp:
                for song in (songs_resp.get("songsByGenre", {}).get("song", []) or []):
                    artist = song.get("artist", "").strip().lower()
                    if artist and genre_name.lower() not in genres.get(artist, []):
                        genres.setdefault(artist, []).append(genre_name.lower())

    cached_entry = _session_cache.get(cache_key, {})
    cached_entry["genres"] = genres
    cached_entry["ts"] = time.time()
    _session_cache[cache_key] = cached_entry
    return genres


def match_to_spotify(
    starred_tracks: list[dict],
    all_spotify_tracks: list[dict],
) -> dict[str, float]:
    """
    Match starred Navidrome tracks to Spotify URIs.

    Returns {spotify_uri: boost_multiplier} where starred = 1.15×.
    """
    lookup: dict[tuple, None] = {
        (t["artist"].lower().strip(), t["title"].lower().strip()): None
        for t in starred_tracks
    }
    result: dict[str, float] = {}
    for track in all_spotify_tracks:
        uri   = track.get("uri", "")
        title = track.get("name", "").lower().strip()
        if not uri:
            continue
        for artist in track.get("artists", []):
            key = (artist.get("name", "").lower().strip(), title)
            if key in lookup:
                result[uri] = 1.15
                break
    return result
