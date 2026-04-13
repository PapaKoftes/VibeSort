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

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

_ROOT           = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH      = os.path.join(_ROOT, "outputs", ".lastfm_cache.json")
SESSION_PATH    = os.path.join(_ROOT, "outputs", ".lastfm_session.json")
BASE_URL        = "https://ws.audioscrobbler.com/2.0/"
AUTH_URL        = "https://www.last.fm/api/auth/"
CALLBACK_URL    = "https://papakoftes.github.io/VibeSort/callback.html"

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
                data.setdefault("artists",    {})
                data.setdefault("tracks",     {})
                data.setdefault("tag_charts", {})
                data.setdefault("similar",    {})   # M2.7: getSimilar results
                return data
        except Exception:
            pass
    return {"artists": {}, "tracks": {}, "tag_charts": {}, "similar": {}}


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


# ---- Tag chart lookup (M1.3 — mood ground truth) ----------------------------

def get_tag_top_tracks(
    tag: str,
    limit: int = 100,
    api_key: str = "",
    cache: dict = None,
) -> list[dict]:
    """
    Fetch the top tracks for a Last.fm tag (human-curated mood ground truth).

    Uses tag.getTopTracks API endpoint.  These are the tracks the Last.fm
    community has most strongly associated with a given tag (e.g. "heartbreak",
    "late night drive", "workout").

    Args:
        tag:     Last.fm tag string (lowercase, spaces OK — e.g. "heartbreak")
        limit:   Number of tracks to fetch (max 1000; 100 is the useful ceiling)
        api_key: Last.fm API key.  Returns [] if empty.
        cache:   In-memory cache dict (modified in place, must call _save_cache)

    Returns:
        [{"artist": str, "title": str, "mbid": str|None, "playcount": int}, ...]
        List ordered by Last.fm playcount rank for that tag.
    """
    if not api_key or not api_key.strip():
        return []

    cache_key = f"{tag.lower().strip()}:{limit}"
    if cache is not None and cache_key in cache.get("tag_charts", {}):
        return cache["tag_charts"][cache_key]

    data = _api_get("tag.getTopTracks", {"tag": tag, "limit": limit}, api_key)
    if data is None:
        return []  # transient failure — do not cache, retry next scan

    raw_tracks = (data.get("tracks") or {}).get("track") or []
    if isinstance(raw_tracks, dict):
        raw_tracks = [raw_tracks]  # Last.fm returns dict when only 1 result

    result: list[dict] = []
    for t in raw_tracks:
        artist_obj = t.get("artist") or {}
        artist_name = (
            artist_obj.get("name", "") if isinstance(artist_obj, dict) else str(artist_obj)
        ).strip()
        title = (t.get("name") or "").strip()
        mbid  = (t.get("mbid") or "").strip() or None
        try:
            playcount = int(t.get("playcount") or 0)
        except (ValueError, TypeError):
            playcount = 0

        if artist_name and title:
            result.append({
                "artist":    artist_name,
                "title":     title,
                "mbid":      mbid,
                "playcount": playcount,
            })

    if cache is not None and result:
        cache.setdefault("tag_charts", {})[cache_key] = result

    return result


# ---- Similar-track mood inference (M2.7) ------------------------------------

# Confidence multiplier for similar-inferred tags.
# Below direct track tags (1.0×) and tag-chart anchor tags (0.75×).
_SIMILAR_CONFIDENCE = 0.55


def get_similar_track_tags(
    artist: str,
    title: str,
    api_key: str,
    limit: int = 5,
    cache: dict | None = None,
) -> dict[str, float]:
    """
    Infer mood tags for a low-confidence track via track.getSimilar.

    Algorithm:
      1. Call track.getSimilar (cached permanently under "similar" sub-cache).
      2. For each similar track (up to `limit`, sorted by match score):
         look up or fetch its top tags via get_track_tags().
      3. Blend tags weighted by match score, normalise, scale to
         _SIMILAR_CONFIDENCE (0.55×) so they rank below direct lookups.

    Args:
        artist:  Artist name.
        title:   Track title.
        api_key: Last.fm API key.
        limit:   Max similar tracks to use (default 5).
        cache:   Shared in-memory cache dict (caller should call _save_cache).

    Returns:
        {tag: weight} or {} if no similar tracks could be resolved.
    """
    if not api_key or not artist or not title:
        return {}

    # ── Step 1: fetch similar tracks ─────────────────────────────────────────
    sim_key = f"sim|||{_normalize_tag(artist)}|||{_normalize_tag(title)}"
    if cache is not None and sim_key in cache.get("similar", {}):
        similar = cache["similar"][sim_key]
    else:
        data = _api_get(
            "track.getSimilar",
            {"artist": artist, "track": title, "limit": limit},
            api_key,
        )
        if data is None:
            return {}   # transient failure — don't cache
        raw = (data.get("similartracks") or {}).get("track") or []
        if isinstance(raw, dict):
            raw = [raw]  # Last.fm single-result edge case

        similar: list[dict] = []
        for t in raw:
            name = (t.get("name") or "").strip()
            art_obj  = t.get("artist") or {}
            art_name = (
                art_obj.get("name", "") if isinstance(art_obj, dict) else str(art_obj)
            ).strip()
            try:
                match = float(t.get("match") or 0)
            except (ValueError, TypeError):
                match = 0.0
            if name and art_name and match > 0:
                similar.append({"artist": art_name, "title": name, "match": match})

        if cache is not None:
            cache.setdefault("similar", {})[sim_key] = similar

    if not similar:
        return {}

    # ── Step 2: blend similar-track tag scores weighted by match ─────────────
    blended: dict[str, float] = {}
    total_match = 0.0

    for sim in similar:
        sim_tags = get_track_tags(sim["artist"], sim["title"], api_key, cache=cache)
        if not sim_tags:
            continue
        m = sim["match"]
        total_match += m
        for tag, w in sim_tags.items():
            blended[tag] = blended.get(tag, 0.0) + w * m

    if not blended or total_match <= 0:
        return {}

    # Normalise by total match, then apply confidence discount
    return {
        tag: round(min(1.0, (s / total_match) * _SIMILAR_CONFIDENCE), 4)
        for tag, s in blended.items()
        if s > 0
    }


# ---- Library-internal similarity graph (Pillar 1) ---------------------------

def get_library_neighbors(
    artist: str,
    title: str,
    api_key: str,
    library_lookup: dict,
    limit: int = 20,
    cache: dict | None = None,
) -> list[tuple[str, float]]:
    """
    Find library-internal similar tracks via track.getSimilar.

    For each similar track returned by Last.fm, check if it exists in the
    user's library via library_lookup.  Only library hits are returned.

    Args:
        artist:         Artist name of the source track.
        title:          Track title of the source track.
        api_key:        Last.fm API key.
        library_lookup: {(artist_lower, clean_title_lower): uri} — built once
                        from all library tracks before the graph pass.
        limit:          Max similar tracks to request from Last.fm (default 20;
                        more → more library hits at the cost of one extra API call).
        cache:          Shared in-memory cache dict (same object used everywhere).

    Returns:
        List of (uri, match_score) for library tracks similar to the source,
        sorted descending by match score.  Empty list on failure or no hits.
    """
    if not api_key or not artist or not title:
        return []

    sim_key = f"sim|||{_normalize_tag(artist)}|||{_normalize_tag(title)}"
    if cache is not None and sim_key in cache.get("similar", {}):
        similar = cache["similar"][sim_key]
    else:
        data = _api_get(
            "track.getSimilar",
            {"artist": artist, "track": title, "limit": limit},
            api_key,
        )
        if data is None:
            return []
        raw = (data.get("similartracks") or {}).get("track") or []
        if isinstance(raw, dict):
            raw = [raw]

        similar: list[dict] = []
        for t in raw:
            name = (t.get("name") or "").strip()
            art_obj  = t.get("artist") or {}
            art_name = (
                art_obj.get("name", "") if isinstance(art_obj, dict) else str(art_obj)
            ).strip()
            try:
                match = float(t.get("match") or 0)
            except (ValueError, TypeError):
                match = 0.0
            if name and art_name and match > 0:
                similar.append({"artist": art_name, "title": name, "match": match})

        if cache is not None:
            cache.setdefault("similar", {})[sim_key] = similar

    if not similar:
        return []

    # Cross-reference against library_lookup
    import re as _re2
    _feat_pat = _re2.compile(
        r"\s*[\(\[\{].*?[\)\]\}]|\s+feat\..*$|\s+ft\..*$",
        _re2.IGNORECASE,
    )

    def _clean(s: str) -> str:
        return _feat_pat.sub("", s).strip().lower()

    hits: list[tuple[str, float]] = []
    for sim in similar:
        key = (_clean(sim["artist"]), _clean(sim["title"]))
        uri = library_lookup.get(key)
        if uri:
            hits.append((uri, sim["match"]))

    hits.sort(key=lambda x: -x[1])
    return hits


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
        "artists_cached":    len(c.get("artists",    {})),
        "tracks_cached":     len(c.get("tracks",     {})),
        "tag_charts_cached": len(c.get("tag_charts", {})),
        "similar_cached":    len(c.get("similar",    {})),
        "cache_path":        CACHE_PATH,
    }


# ── Web authentication (user "Sign in with Last.fm") ─────────────────────────
#
# How it works (identical pattern to Spotify PKCE):
#   1. generate_auth_url(api_key)  → redirect user to last.fm to approve
#   2. Last.fm redirects to CALLBACK_URL?token=TOKEN
#   3. GitHub Pages passes all query params to localhost (existing callback.html)
#   4. app.py intercepts ?token= → stores in session_state["_pending_lastfm_token"]
#   5. Connect page calls exchange_token(token, api_key, api_secret) → session_key
#   6. Session key + username stored via save_session()
#
# Developer setup (one-time):
#   Register a Vibesort Last.fm app at https://www.last.fm/api/account/create
#   Set VIBESORT_LASTFM_API_KEY and VIBESORT_LASTFM_API_SECRET in config.py.
#   End users never need to touch Last.fm's developer tools.

def _sign(params: dict, secret: str) -> str:
    """
    Compute Last.fm API signature (md5 of sorted key+value pairs + secret).
    'format' and 'callback' parameters are excluded from the signature per spec.
    """
    exclude = {"format", "callback"}
    sig_str = "".join(
        f"{k}{v}"
        for k, v in sorted(params.items())
        if k not in exclude
    ) + secret
    return hashlib.md5(sig_str.encode("utf-8")).hexdigest()


def generate_auth_url(api_key: str) -> str:
    """Return the Last.fm web-auth URL to redirect the user to."""
    params = urllib.parse.urlencode({
        "api_key":  api_key,
        "cb":       CALLBACK_URL,
    })
    return f"{AUTH_URL}?{params}"


def exchange_token(token: str, api_key: str, api_secret: str) -> dict | None:
    """
    Exchange a web-auth token for a session key.

    Returns {"key": session_key, "name": lastfm_username} or None on failure.
    Requires api_secret to sign the request — this is the developer's shared secret,
    not the user's password.
    """
    if not token or not api_key or not api_secret:
        return None
    params = {
        "method":  "auth.getSession",
        "api_key": api_key,
        "token":   token,
    }
    params["api_sig"] = _sign(params, api_secret)
    params["format"]  = "json"

    _rate_limit()
    try:
        req = urllib.request.Request(
            BASE_URL,
            data=urllib.parse.urlencode(params).encode("utf-8"),
            headers={
                "User-Agent":   "Vibesort/1.0 (github.com/PapaKoftes/VibeSort)",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "error" in data:
            return None
        sess = data.get("session", {})
        return {"key": sess.get("key", ""), "name": sess.get("name", "")} or None
    except Exception:
        return None


def save_session(session: dict) -> None:
    """Persist the session key + username to disk."""
    try:
        os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
        with open(SESSION_PATH, "w", encoding="utf-8") as f:
            json.dump(session, f)
    except Exception:
        pass


def load_session() -> dict | None:
    """Load persisted Last.fm session from disk. Returns None if absent/invalid."""
    try:
        if os.path.exists(SESSION_PATH):
            with open(SESSION_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("key") and data.get("name"):
                return data
    except Exception:
        pass
    return None


def clear_session() -> None:
    """Remove the persisted Last.fm session (disconnect)."""
    try:
        if os.path.exists(SESSION_PATH):
            os.remove(SESSION_PATH)
    except Exception:
        pass


def get_user_loved_tracks(
    session_key: str,
    api_key: str,
    username: str,
    limit: int = 200,
) -> dict[str, float]:
    """
    Fetch the user's loved tracks from Last.fm.

    Returns {(artist_norm, title_norm): boost_weight} where boost_weight is
    always 1.0 (binary — track is loved).  Used in scan to apply a score
    multiplier to loved tracks.
    """
    if not session_key or not api_key or not username:
        return {}

    loved: dict[str, float] = {}
    page = 1
    fetched = 0

    while fetched < limit:
        per_page = min(200, limit - fetched)
        data = _api_get(
            "user.getlovedtracks",
            {"user": username, "limit": str(per_page), "page": str(page)},
            api_key,
        )
        if not data:
            break
        tracks = (data.get("lovedtracks") or {}).get("track", [])
        if isinstance(tracks, dict):
            tracks = [tracks]
        if not tracks:
            break
        for t in tracks:
            artist = _normalize_tag((t.get("artist") or {}).get("name", ""))
            title  = _normalize_tag(t.get("name", ""))
            if artist and title:
                loved[f"{artist}|||{title}"] = 1.0
        fetched += len(tracks)
        page += 1
        if len(tracks) < per_page:
            break

    return loved


def get_user_top_tracks(
    api_key: str,
    username: str,
    period: str = "6month",
    limit: int = 200,
) -> dict[str, float]:
    """
    Fetch user's top tracks from Last.fm (by play count in the given period).

    Returns {(artist_norm, title_norm): normalised_weight} where weight is
    play_count / max_play_count in [0, 1].  Used for score boosting.
    period: overall | 7day | 1month | 3month | 6month | 12month
    """
    if not api_key or not username:
        return {}

    data = _api_get(
        "user.gettoptracks",
        {"user": username, "period": period, "limit": str(min(limit, 1000))},
        api_key,
    )
    if not data:
        return {}

    tracks = (data.get("toptracks") or {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]
    if not tracks:
        return {}

    raw: list[tuple[str, int]] = []
    for t in tracks:
        artist = _normalize_tag((t.get("artist") or {}).get("name", ""))
        title  = _normalize_tag(t.get("name", ""))
        count  = int((t.get("playcount") or "0").strip() if isinstance(t.get("playcount"), str) else t.get("playcount") or 0)
        if artist and title and count > 0:
            raw.append((f"{artist}|||{title}", count))

    if not raw:
        return {}

    max_count = max(c for _, c in raw) or 1
    return {key: round(count / max_count, 4) for key, count in raw}


# ── TOD: time-of-day scrobble buckets ─────────────────────────────────────────
# Maps hour → bucket name used as a pseudo-tag prefix (tod_<bucket>).
_TOD_BUCKETS: dict[str, range] = {
    "late_night": range(0, 6),    # 00:00 – 05:59
    "morning":    range(6, 12),   # 06:00 – 11:59
    "afternoon":  range(12, 18),  # 12:00 – 17:59
    "evening":    range(18, 24),  # 18:00 – 23:59
}


def get_recent_tracks_tod(
    api_key: str,
    username: str,
    limit: int = 1000,
) -> dict[str, dict[str, float]]:
    """
    Fetch recent scrobbles for a user and bucket each track by time of day.

    Returns:
        {"artist|||title_norm": {"late_night": 0.8, "morning": 0.2, ...}}

    Each inner dict has normalised weights per bucket (sum to 1.0).
    Only tracks with ≥3 scrobbles are included (below that, timing is noise).
    """
    if not api_key or not username:
        return {}

    from datetime import datetime, timezone

    raw: dict[str, dict[str, int]] = {}  # key → {bucket: count}
    page = 1
    fetched = 0
    per_page = min(200, limit)

    while fetched < limit:
        data = _api_get(
            "user.getrecenttracks",
            {
                "user": username,
                "limit": str(per_page),
                "page":  str(page),
                "extended": "0",
            },
            api_key,
        )
        if not data:
            break

        tracks = (data.get("recenttracks") or {}).get("track", [])
        if isinstance(tracks, dict):
            tracks = [tracks]
        if not tracks:
            break

        added = 0
        for t in tracks:
            # Skip currently-playing stub (no timestamp)
            if t.get("@attr", {}).get("nowplaying"):
                continue
            ts_str = (t.get("date") or {}).get("uts", "")
            if not ts_str:
                continue
            try:
                ts = int(ts_str)
            except (ValueError, TypeError):
                continue

            artist = _normalize_tag((t.get("artist") or {}).get("#text", ""))
            title  = _normalize_tag(t.get("name", ""))
            if not artist or not title:
                continue

            hour = datetime.fromtimestamp(ts, tz=timezone.utc).hour
            bucket = next(
                (b for b, rng in _TOD_BUCKETS.items() if hour in rng),
                "evening",
            )
            key = f"{artist}|||{title}"
            raw.setdefault(key, {b: 0 for b in _TOD_BUCKETS})
            raw[key][bucket] += 1
            added += 1

        fetched += added
        page += 1
        if added < per_page:
            break

    # Normalise to weights, filter low-count tracks
    result: dict[str, dict[str, float]] = {}
    for key, bucket_counts in raw.items():
        total = sum(bucket_counts.values())
        if total < 3:
            continue
        result[key] = {b: round(c / total, 4) for b, c in bucket_counts.items()}

    return result
