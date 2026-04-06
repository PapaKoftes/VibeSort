"""
maloja.py — Maloja self-hosted scrobble server integration.

Maloja is an open-source Last.fm alternative that users self-host.
https://github.com/krateng/maloja

WHAT THIS PRODUCES
==================
Play-count boosts for tracks the user has listened to frequently.
Same mechanism as ListenBrainz: matched tracks get a _lb_top_uris
multiplier of 1.05–1.20 so they bubble up in playlists.

MALOJA API
==========
v3.x endpoints used:
  GET /api/0/charts/tracks?page=1&perpage=500  → top tracks with scrobble counts
  GET /api/0/serverinfo                         → verify server is reachable + get name

Authentication: ?key=TOKEN query param (or Authorization: Bearer TOKEN header).
Both work; we use query param for simplicity.

CONFIG (.env or Settings)
=========================
  MALOJA_URL=http://localhost:42010    # your Maloja server URL (no trailing slash)
  MALOJA_TOKEN=your_api_token          # from Maloja admin → Settings → API

SETUP
=====
  1. Run Maloja (https://github.com/krateng/maloja#how-to-run)
  2. Enable API access in Maloja settings and copy the token
  3. Paste URL + token in Settings → Connect, or add to .env

RATE LIMIT / CACHE
==================
Single paginated request — no rate-limiting needed.
Results cached for 6 hours per scan session (memory only, no disk cache needed
because Maloja is local/LAN, so re-requests are fast).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

_REQUEST_TIMEOUT = 10

# ── Helpers ──────────────────────────────────────────────────────────────────

def _get(url: str, token: str, params: dict | None = None) -> dict | None:
    """GET a Maloja API endpoint. Returns parsed JSON or None on error."""
    qs = urllib.parse.urlencode({**(params or {}), "key": token})
    full_url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"
    req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


# ── Public API ───────────────────────────────────────────────────────────────

def ping(base_url: str, token: str) -> dict | None:
    """
    Verify the server is reachable and the token works.

    Returns {"name": str, "version": str} on success, None on failure.
    """
    base_url = base_url.rstrip("/")
    data = _get(f"{base_url}/api/0/serverinfo", token)
    if data and isinstance(data, dict):
        return {
            "name":    data.get("name", "Maloja"),
            "version": data.get("version", "?"),
        }
    return None


def top_tracks(
    base_url: str,
    token: str,
    max_tracks: int = 500,
) -> list[dict]:
    """
    Fetch the user's most-played tracks from Maloja.

    Returns list of {"artist": str, "title": str, "scrobbles": int}.
    """
    base_url = base_url.rstrip("/")
    results: list[dict] = []
    page = 1
    per_page = min(200, max_tracks)

    while len(results) < max_tracks:
        data = _get(
            f"{base_url}/api/0/charts/tracks",
            token,
            {"page": page, "perpage": per_page, "timerange": "alltime"},
        )
        if not data:
            break
        entries = data.get("list", []) or data.get("tracks", []) or []
        if not entries:
            break
        for entry in entries:
            track = entry.get("track") or entry
            artists = track.get("artists") or track.get("artist") or []
            if isinstance(artists, str):
                artists = [artists]
            artist = artists[0] if artists else ""
            title  = track.get("title", "") or track.get("name", "")
            scrobbles = int(entry.get("scrobbles", entry.get("count", 1)))
            if artist and title:
                results.append({"artist": artist, "title": title, "scrobbles": scrobbles})
        if len(entries) < per_page:
            break
        page += 1

    return results[:max_tracks]
