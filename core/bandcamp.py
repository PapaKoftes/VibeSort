"""
bandcamp.py — Bandcamp collection scraper for underground taste signal.

Bandcamp purchases and wishlist items are strong signals for underground/indie
taste — genres and styles unavailable from Spotify/Last.fm.

HOW IT WORKS
============
1. Scrape the user's Bandcamp collection page (public or with session cookies)
2. Extract artist + album entries
3. Match each to MusicBrainz by artist+album → get genre/style tags
4. Feed tags into artist_genres_map for profile building

WHAT WE SCRAPE
==============
  https://bandcamp.com/{username}/  — purchase/collection page
  Each item has artist name, album title, and tags the artist self-assigned.

NO OFFICIAL API
===============
Bandcamp has no public API for user collections. We parse the embedded JSON-LD
and data attributes from the HTML — this is the same data shown to the user.
Only the user's own public collection is accessed (no auth required if public).

RATE LIMITING
=============
Single page load only. No polling. Cached to disk.

CACHE
=====
outputs/.bandcamp_cache.json — keyed by username, TTL 24h.

CONFIG (.env or Settings → Enrichment Sources)
===============================================
  BANDCAMP_USERNAME=yourusername  # your Bandcamp username (the one in your URL)
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".bandcamp_cache.json")
_CACHE_TTL = 86400  # 24h

_REQUEST_TIMEOUT = 15
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ── Cache ─────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_cache(data: dict) -> None:
    try:
        from core.cache_io import atomic_write_json
        atomic_write_json(CACHE_PATH, data)
    except OSError:
        pass


# ── Scraper ───────────────────────────────────────────────────────────────────

def _fetch_html(url: str) -> str | None:
    req = urllib.request.Request(
        url, headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError):
        return None


def _parse_collection(html: str) -> list[dict]:
    """
    Extract collection items from Bandcamp collection page HTML.

    Returns list of {"artist": str, "album": str, "tags": list[str]}.
    """
    items: list[dict] = []

    # Method 1: try data-blob JSON embedded in page
    m = re.search(r'data-blob="([^"]+)"', html)
    if m:
        try:
            blob_raw = m.group(1).replace("&quot;", '"').replace("&#39;", "'")
            blob = json.loads(blob_raw)
            collection = (
                blob.get("collection_data", {}).get("redownload_urls", {})
                or blob.get("item_cache", {}).get("collection", {})
            )
            if isinstance(collection, dict):
                for item_id, item in collection.items():
                    artist = item.get("band_name") or item.get("artist", "")
                    album  = item.get("album_title") or item.get("item_title", "")
                    tags   = item.get("genre_id_list") or []
                    if artist:
                        items.append({"artist": artist, "album": album, "tags": [str(t) for t in tags]})
        except (json.JSONDecodeError, AttributeError):
            pass

    # Method 2: fallback — parse individual collection item divs
    if not items:
        for m2 in re.finditer(
            r'class="[^"]*collection-item-container[^"]*"[^>]*'
            r'data-band-name="([^"]+)"[^>]*data-item-title="([^"]*)"',
            html,
        ):
            artist = urllib.parse.unquote(m2.group(1))
            album  = urllib.parse.unquote(m2.group(2))
            if artist:
                items.append({"artist": artist, "album": album, "tags": []})

    # Method 3: JSON-LD
    if not items:
        for m3 in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
            try:
                ld = json.loads(m3.group(1))
                if ld.get("@type") in ("MusicAlbum", "MusicRecording"):
                    artist = ""
                    by = ld.get("byArtist") or ld.get("creator")
                    if isinstance(by, dict):
                        artist = by.get("name", "")
                    elif isinstance(by, str):
                        artist = by
                    album = ld.get("name", "")
                    tags  = [g.strip() for g in (ld.get("genre") or [])]
                    if artist:
                        items.append({"artist": artist, "album": album, "tags": tags})
            except (json.JSONDecodeError, AttributeError):
                pass

    return items


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_collection(username: str) -> list[dict]:
    """
    Fetch a user's Bandcamp collection.

    Returns list of {"artist": str, "album": str, "tags": list[str]}.
    Uses cache with 24h TTL.
    """
    username = username.strip().lower()
    if not username:
        return []

    cache = _load_cache()
    cached = cache.get(username)
    if cached and isinstance(cached, dict):
        ts = cached.get("ts", 0)
        if time.time() - ts < _CACHE_TTL:
            return cached.get("items", [])

    url = f"https://bandcamp.com/{urllib.parse.quote(username)}/"
    html = _fetch_html(url)
    if not html:
        return []

    items = _parse_collection(html)
    cache[username] = {"ts": time.time(), "items": items}
    _save_cache(cache)
    return items


def collection_to_artist_tags(items: list[dict]) -> dict[str, list[str]]:
    """
    Convert collection items to {artist_name_lower: [genre_tag, ...]} for
    merging into artist_genres_map (matched by name, not Spotify ID).

    Tags from Bandcamp are often raw genre strings like "electronic", "ambient",
    "post-rock" which feed directly into to_macro() for macro-genre mapping.
    """
    result: dict[str, list[str]] = {}
    for item in items:
        artist = item.get("artist", "").strip()
        tags   = item.get("tags", [])
        if not artist:
            continue
        key = artist.lower()
        if key not in result:
            result[key] = []
        for tag in tags:
            t = str(tag).lower().strip()
            if t and t not in result[key]:
                result[key].append(t)
    return result
