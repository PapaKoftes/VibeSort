"""
deezer.py — Deezer public API artist genre + per-track data enrichment (no API key required).

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

PER-TRACK DATA (M1.2)
======================
get_track_data_batch() fetches per-track signals from Deezer:
  - bpm          (int|None)   — real tempo, not proxied
  - explicit     (bool)       — Parental Advisory flag
  - rank         (int)        — Deezer popularity rank
  - gain         (float|None) — replay-gain value
  - contributors (list[dict]) — feat. artists with role labels

Non-English fallback strategy (K-pop, Arabic, J-pop, etc.):
  Attempt 1: artist:"<name>" track:"<title>"  (exact quoted)
  Attempt 2: artist:<name> track:<title>       (unquoted if 0 results)
  Attempt 3: track:"<title>"                   (title only, if ASCII)
  Attempt 4: skip, log as "no_match" in cache

Matching: difflib.SequenceMatcher, title similarity >= 0.8 AND artist >= 0.7.

RATE LIMIT
==========
Conservative 150ms gap (approx. 6 req/sec).  Deezer's undocumented limit is ~50/5s.
First run for 300 artists (approx. 900 calls): ~135 seconds.  Subsequent runs: instant.
Per-track first run for 2000 tracks: approx. 300 seconds (cached permanently after).

CACHE
=====
outputs/.deezer_cache.json — persistent, shared across runs.
  "artists": { "<artist_lower>": ["Genre1", "Genre2"] }
  "tracks":  { "<artist_lower>|||<title_lower>": { "bpm": 128, "explicit": true, ... } }
"""

from __future__ import annotations

import difflib
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
                d.setdefault("tracks", {})
                return d
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


# ── Per-track data (M1.2) ─────────────────────────────────────────────────────

def _track_cache_key(artist_name: str, title: str) -> str:
    return f"{artist_name.lower().strip()}|||{title.lower().strip()}"


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _search_track(artist_name: str, title: str) -> dict | None:
    """
    Search Deezer for a single track using a 4-attempt fallback strategy.

    Returns the best-matching Deezer track dict, or None if no match found.
    Title similarity >= 0.8 AND artist similarity >= 0.7 required to accept.
    """
    attempts: list[str] = []

    # Attempt 1: exact quoted search
    q1 = urllib.parse.urlencode({"q": f'artist:"{artist_name}" track:"{title}"', "limit": 5})
    attempts.append(f"search?{q1}")

    # Attempt 2: unquoted (better for non-ASCII names)
    q2 = urllib.parse.urlencode({"q": f"artist:{artist_name} track:{title}", "limit": 5})
    attempts.append(f"search?{q2}")

    # Attempt 3: title-only (if title is ASCII)
    if title.isascii():
        q3 = urllib.parse.urlencode({"q": f'track:"{title}"', "limit": 5})
        attempts.append(f"search?{q3}")

    for path in attempts:
        hit = _get(path)
        if hit is None:
            return None  # transient failure — don't try remaining attempts
        results = hit.get("data") or []
        if not results:
            continue

        # Pick the best match by title + artist similarity
        best_score = 0.0
        best_track = None
        for r in results:
            t_sim = _similarity(r.get("title", ""), title)
            a_sim = _similarity((r.get("artist") or {}).get("name", ""), artist_name)
            if t_sim >= 0.8 and a_sim >= 0.7:
                score = t_sim * 0.6 + a_sim * 0.4
                if score > best_score:
                    best_score = score
                    best_track = r
        if best_track is not None:
            return best_track

    return None  # all attempts exhausted


def _extract_track_data(deezer_track: dict) -> dict:
    """Extract the signals we care about from a raw Deezer track dict."""
    return {
        "bpm":          deezer_track.get("bpm") or None,
        "explicit":     bool(deezer_track.get("explicit_lyrics", False)),
        "rank":         deezer_track.get("rank") or 0,
        "gain":         deezer_track.get("gain") or None,
        "contributors": [
            {"name": c.get("name", ""), "role": c.get("role", "")}
            for c in (deezer_track.get("contributors") or [])
        ],
    }


def get_track_data(artist_name: str, title: str, cache: dict = None) -> dict | None:
    """
    Fetch per-track data for a single track from Deezer.

    Returns a dict with keys: bpm, explicit, rank, gain, contributors.
    Returns None on transient failure (caller should not cache).
    Returns {} on confirmed no-match (caller may cache as sentinel).
    """
    key = _track_cache_key(artist_name, title)

    if cache is not None:
        cached = cache.get("tracks", {}).get(key)
        if cached is not None:
            return cached if cached != "no_match" else {}

    result = _search_track(artist_name, title)

    if result is None:
        return None  # transient — don't cache

    if not result:
        # Confirmed no match found after all attempts
        if cache is not None:
            cache.setdefault("tracks", {})[key] = "no_match"
        return {}

    data = _extract_track_data(result)
    if cache is not None:
        cache.setdefault("tracks", {})[key] = data
    return data


def get_track_data_batch(
    tracks: list[dict],
    existing: dict = None,
    progress_fn=None,
) -> dict[str, dict]:
    """
    Fetch per-track Deezer data (BPM, explicit, rank, gain, contributors) for a
    list of library tracks.

    Args:
        tracks:      List of track dicts with at minimum "uri", "name", and "artists" keys.
        existing:    {uri: data} already fetched — these are skipped.
        progress_fn: Optional callable(msg: str) for UI progress updates.

    Returns:
        {uri: {"bpm": int|None, "explicit": bool, "rank": int, "gain": float|None,
               "contributors": [{"name": str, "role": str}]}}
        Only URIs with a successful match are included.
    """
    cache    = _load_cache()
    existing = existing or {}

    todo = [
        t for t in tracks
        if t.get("uri") and t.get("name") and t.get("artists")
        and t["uri"] not in existing
    ]

    total   = len(todo)
    result: dict[str, dict] = {}

    if total == 0:
        return result

    est_secs = int(total * _RATE_GAP)
    print(
        f"\n  Deezer per-track data  {total} tracks to fetch"
        f" (first run only — cached permanently afterwards, ~{est_secs}s)"
    )

    for i, track in enumerate(todo):
        if progress_fn and (i % 20 == 0 or i == total - 1):
            progress_fn(f"Deezer track data  {i+1}/{total}: {track.get('name', '')[:30]}")

        artist_name = (track.get("artists") or [{}])[0].get("name", "")
        title       = track.get("name", "")

        if not artist_name or not title:
            continue

        data = get_track_data(artist_name, title, cache=cache)
        if data:  # non-empty dict = real match
            result[track["uri"]] = data

    _save_cache(cache)

    matched = len(result)
    print(f"  Deezer per-track data  {matched}/{total} tracks matched")
    return result


def get_artist_top_tracks(artist_name: str, limit: int = 50) -> list[dict]:
    """
    Fetch up to `limit` top tracks for an artist from Deezer via search.

    Returns list of raw Deezer track dicts (with bpm, rank, etc.).
    Useful for bulk BPM acquisition when individual track lookup is too slow.
    """
    q   = urllib.parse.urlencode({"q": f'artist:"{artist_name}"', "limit": min(limit, 100)})
    hit = _get(f"search?{q}")
    if not hit:
        return []
    results = hit.get("data") or []
    # Filter to tracks where artist matches reasonably well
    key = artist_name.lower().strip()
    return [
        r for r in results
        if _similarity((r.get("artist") or {}).get("name", ""), key) >= 0.7
    ]


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
