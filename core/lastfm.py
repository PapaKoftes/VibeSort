"""
lastfm.py — Last.fm API enrichment for artist genre and track mood tags.

WHY THIS EXISTS
===============
In Spotify's Development Mode (post-Nov 2024):
  - audio-features endpoint          -> 403 (deprecated)
  - batch /artists?ids= endpoint     -> 403 (blocked)
  - individual /artists/{id}         -> returns empty genres for most artists
  - /playlist_items on 3rd-party     -> 403 (blocked)

This leaves the scorer with zero signal -> 0 moods for most users.

Last.fm solves ALL of this:
  - Works completely independently of Spotify
  - Has crowd-sourced genre AND mood tags for virtually every artist/track
  - Returns human-language descriptors that directly match Vibesort's
    expected_tags in packs.json  ("sad", "dark", "chill", "energetic" ...)
  - Tag data is richer than Spotify's sparse genre system
  - Free API key, no extra Python packages required (pure stdlib urllib)

SETUP
=====
  1. https://www.last.fm/api/account/create  (free, 30 seconds)
  2. Create application -> copy the API key
  3. Set LASTFM_API_KEY=<key> in your .env file

ARCHITECTURE
============
  artist.getTopTags  -> raw genre tags ("hip hop", "electronic", "indie rock")
      -> fed into artist_genres_map as-is
      -> to_macro() maps them to MACRO_GENRES via macro_genres.json rules
      -> fixes genre_map:  1 genre  ->  20+ genres

  track.getTopTags   -> mood + genre tags ("sad", "dark", "workout", "late night")
      -> fed into track_tags for scorer.tag_score()
      -> fixes mood detection:  0 moods  ->  meaningful moods

Rate: 5 req/sec enforced internally.
Cache: outputs/.lastfm_cache.json (persistent, shared with future runs).
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".lastfm_cache.json")
BASE_URL   = "https://ws.audioscrobbler.com/2.0/"

# Tags that add zero signal -- generic filler that Last.fm users add
_SKIP_TAGS: frozenset = frozenset({
    "seen live", "under 2000 listeners", "favorites", "favourite", "favorite",
    "all", "albums i own", "beautiful", "awesome", "good", "great", "love",
    "heard on pandora", "spotify", "youtube", "vevo", "amazing", "best",
    "cool", "nice", "like", "liked", "loved", "top", "sexy", "music",
    "songs", "playlist", "mix", "tracks", "hits", "classical music",
})


# ---- Cache ------------------------------------------------------------------

def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("artists", {})
                data.setdefault("tracks",  {})
                return data
        except Exception:
            pass
    return {"artists": {}, "tracks": {}}


def _save_cache(cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass


# ---- HTTP -------------------------------------------------------------------

_last_request_time: float = 0.0


def _rate_limit() -> None:
    """Enforce ~5 req/sec ceiling (210ms minimum gap between calls)."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < 0.21:
        time.sleep(0.21 - elapsed)
    _last_request_time = time.monotonic()


def _api_get(method: str, params: dict, api_key: str) -> dict | None:
    """
    Single Last.fm API call.

    Returns:
      - parsed JSON dict on success
      - {} when Last.fm explicitly returns an error response (e.g. artist not found)
        → caller may cache this as "confirmed no data"
      - None on transient network/parse failures
        → caller should NOT cache; will retry on next scan
    """
    _rate_limit()
    p = dict(params)
    p.update({"method": method, "api_key": api_key, "format": "json"})
    url = BASE_URL + "?" + urllib.parse.urlencode(p)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Vibesort/1.0 (github.com/PapaKoftes/VibeSort)"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        if "error" in data:
            return {}   # Last.fm confirmed "not found" — safe to cache
        return data
    except urllib.error.HTTPError as _he:
        # 404 = Last.fm confirmed not found — safe to cache as empty.
        # 429 / 403 / 5xx = transient — do NOT cache; retry next scan.
        return {} if _he.code == 404 else None
    except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
        return None   # network failure — don't cache, retry next scan


# ---- Tag parsing ------------------------------------------------------------

def _normalize_tag(tag: str) -> str:
    """Lowercase, strip, replace spaces with underscores."""
    return "_".join(tag.lower().split())


def _parse_tags(tag_data, top_n: int = 15) -> dict:
    """
    Parse Last.fm toptags response into {normalized_tag: weight}.

    tag_data: the 'tag' value inside toptags -- may be list OR single dict
              (Last.fm returns a dict instead of a list when there is only 1 tag)
    top_n:    how many tags to keep after filtering
    Returns weights normalised to [0, 1] relative to the highest count.
    """
    if isinstance(tag_data, dict):
        tag_data = [tag_data]
    if not isinstance(tag_data, list):
        return {}

    raw = []
    for t in tag_data[: top_n * 2]:
        name  = (t.get("name") or "").strip()
        count = int(t.get("count", 0))
        if not name or count < 3:
            continue
        if name.lower() in _SKIP_TAGS:
            continue
        raw.append((_normalize_tag(name), count))

    if not raw:
        return {}

    # De-duplicate: keep highest count per normalised tag
    deduped: dict = {}
    for tag, count in raw:
        if tag not in deduped or count > deduped[tag]:
            deduped[tag] = count

    max_count = max(deduped.values()) or 1
    return {
        tag: round(count / max_count, 4)
        for tag, count in sorted(deduped.items(), key=lambda x: -x[1])[:top_n]
    }


# ---- Single lookups (public, individually cached) ---------------------------

def get_artist_tags(artist_name: str, api_key: str, cache: dict = None) -> dict:
    """
    Fetch top genre/mood tags for an artist from Last.fm.

    Returns {normalized_tag: weight}.
    Writes result into `cache` dict in-place (call _save_cache() after batches).
    Only caches on definitive responses; transient network failures are not cached
    so the next scan will retry.
    """
    key = _normalize_tag(artist_name)
    if cache is not None and key in cache.get("artists", {}):
        return cache["artists"][key]

    data = _api_get("artist.getTopTags", {"artist": artist_name}, api_key)
    if data is None:
        return {}   # Transient failure — don't cache, retry next scan

    tag_data = (data.get("toptags") or {}).get("tag", [])
    result   = _parse_tags(tag_data, top_n=15)

    if cache is not None:
        cache.setdefault("artists", {})[key] = result
    return result


def get_track_tags(artist_name: str, track_title: str,
                   api_key: str, cache: dict = None) -> dict:
    """
    Fetch top mood/genre tags for a specific track from Last.fm.

    Returns {normalized_tag: weight}.
    Only caches on definitive responses; transient failures are not cached.
    """
    key = f"{_normalize_tag(artist_name)}|||{_normalize_tag(track_title)}"
    if cache is not None and key in cache.get("tracks", {}):
        return cache["tracks"][key]

    data = _api_get(
        "track.getTopTags",
        {"artist": artist_name, "track": track_title},
        api_key,
    )
    if data is None:
        return {}   # Transient failure — don't cache

    tag_data = (data.get("toptags") or {}).get("tag", [])
    result   = _parse_tags(tag_data, top_n=12)

    if cache is not None:
        cache.setdefault("tracks", {})[key] = result
    return result


# ---- Library enrichment (main entry point) ----------------------------------

def enrich_library(
    tracks: list,
    api_key: str,
    max_artists: int = 300,
    max_tracks:  int = 300,
    progress_fn=None,
) -> tuple:
    """
    Enrich the full library with Last.fm tags.

    ARTIST TAGS -> artist_genres_map:
        Raw space-separated tag strings ("hip hop", "indie rock", "electronic")
        are returned for direct insertion into artist_genres_map.
        genre.to_macro() can then map them to MACRO_GENRES because
        macro_genres.json rules already cover these common tag strings.
        e.g. "hip hop" -> rule ["hip hop", "East Coast Rap"] -> macro genre set.

    TRACK TAGS -> track_tags for mood scoring:
        Tags like "sad", "dark", "energetic", "late night", "workout" directly
        match packs.json expected_tags and scorer synonym clusters.

    Args:
        tracks:       All library tracks (list of Spotify track dicts).
        api_key:      Last.fm API key.  Empty string -> returns ({}, {}).
        max_artists:  Max unique artists enriched (sorted by library frequency).
        max_tracks:   Max tracks for per-track lookup (sorted by popularity).
        progress_fn:  Optional callable(msg: str) for UI progress updates.

    Returns:
        (artist_raw_tags, track_tags_map)

        artist_raw_tags : {artist_id: ["hip hop", "rap", "dark", ...]}
            Space-separated raw strings for artist_genres_map.

        track_tags_map  : {spotify_uri: {normalized_tag: weight}}
            Per-track tags for scorer.tag_score().
    """
    if not api_key or not api_key.strip():
        return {}, {}

    cache = _load_cache()

    # ---- Rank artists by library frequency ----------------------------------
    artist_freq: dict = {}   # {id: (name, count)}
    for track in tracks:
        for artist in track.get("artists", []):
            aid  = artist.get("id", "")
            name = artist.get("name", "")
            if aid and name:
                prev = artist_freq.get(aid, (name, 0))[1]
                artist_freq[aid] = (name, prev + 1)

    top_artists = sorted(
        artist_freq.items(),
        key=lambda x: -x[1][1],
    )[:max_artists]

    # ---- Artist enrichment --------------------------------------------------
    artist_name_to_tags: dict = {}   # normalised_name -> {tag: weight}
    artist_raw_tags:     dict = {}   # artist_id -> [raw_str, ...]

    total = len(top_artists)
    for i, (aid, (name, _)) in enumerate(top_artists):
        if progress_fn:
            progress_fn(f"Last.fm artist tags  {i+1}/{total}: {name[:32]}")

        tags = get_artist_tags(name, api_key, cache=cache)
        artist_name_to_tags[_normalize_tag(name)] = tags

        # Convert normalised keys back to space-separated raw strings so that
        # genre.to_macro() can apply macro_genres.json rules correctly.
        # "hip_hop" -> "hip hop" -> rule match -> "East Coast Rap"
        artist_raw_tags[aid] = [t.replace("_", " ") for t in tags.keys()]

    _save_cache(cache)   # Flush artist cache after all artist calls

    # ---- Track enrichment ---------------------------------------------------
    sorted_tracks = sorted(
        [t for t in tracks if t.get("uri") and t.get("name")],
        key=lambda t: -t.get("popularity", 0),
    )

    track_tags_map: dict = {}
    enriched = 0

    for track in sorted_tracks:
        uri         = track.get("uri", "")
        title       = track.get("name", "")
        artists     = track.get("artists", [])
        artist_name = artists[0].get("name", "") if artists else ""
        if not uri or not title or not artist_name:
            continue

        # Per-track call (capped at max_tracks)
        if enriched < max_tracks:
            if progress_fn and enriched % 25 == 0:
                n_left = min(max_tracks, len(sorted_tracks))
                progress_fn(
                    f"Last.fm track tags   {enriched+1}/{n_left}"
                    f" -- {artist_name[:20]} -- {title[:20]}"
                )
            t_tags  = get_track_tags(artist_name, title, api_key, cache=cache)
            enriched += 1
        else:
            t_tags = {}

        # Merge: artist tags at 55% weight as baseline,
        #        track-specific tags override at full weight.
        name_key = _normalize_tag(artist_name)
        a_tags   = artist_name_to_tags.get(name_key, {})

        merged: dict = {}
        for tag, w in a_tags.items():
            merged[tag] = round(w * 0.55, 4)
        for tag, w in t_tags.items():
            merged[tag] = max(merged.get(tag, 0.0), w)

        if merged:
            track_tags_map[uri] = merged

    _save_cache(cache)   # Flush track cache

    return artist_raw_tags, track_tags_map


def cache_stats() -> dict:
    """Return info about the current cache state (for debug / scan display)."""
    c = _load_cache()
    return {
        "artists_cached": len(c.get("artists", {})),
        "tracks_cached":  len(c.get("tracks",  {})),
        "cache_path":     CACHE_PATH,
    }
