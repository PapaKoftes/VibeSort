"""
audiodb.py — TheAudioDB enrichment for artist and track mood/genre/style data.

TheAudioDB is a community-maintained music database with editorial-quality
mood, genre, and style labels for artists and tracks.  Unlike Deezer (genres
only) or Last.fm (requires a key), AudioDB provides *direct mood labels* per
artist AND per track for free, with no API key required.

API:  https://theaudiodb.com/api/v1/json/2/
Key:  "2" is the public test key — no registration needed.

Signals provided:
  Artist level:  strGenre, strStyle, strMood
  Track level:   strGenre, strMood, strTheme

All results are cached persistently in outputs/.audiodb_cache.json.
Rate: ~3 req/sec (0.35s gap enforced).
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".audiodb_cache.json")
BASE_URL   = "https://theaudiodb.com/api/v1/json/2/"

# AudioDB mood labels → weighted tag dict using Vibesort's tag vocabulary.
# These feed directly into track_tags and are scored by scorer.tag_score().
_MOOD_TAGS: dict[str, dict[str, float]] = {
    "happy":         {"happy": 1.0, "feel_good": 0.7, "upbeat": 0.6},
    "sad":           {"sad": 1.0, "melancholic": 0.5},
    "melancholic":   {"melancholic": 1.0, "sad": 0.5, "nostalgic": 0.6},
    "dark":          {"dark": 1.0},
    "angry":         {"angry": 1.0, "aggressive": 0.7},
    "energetic":     {"energetic": 1.0, "high_energy": 0.7, "intense": 0.5},
    "calm":          {"calm": 1.0, "chill": 0.7, "relaxed": 0.5},
    "romantic":      {"romantic": 1.0, "love": 0.6},
    "upbeat":        {"upbeat": 1.0, "happy": 0.6, "feel_good": 0.5},
    "epic":          {"epic": 1.0, "cinematic": 0.7},
    "motivational":  {"motivational": 1.0, "uplifting": 0.7},
    "peaceful":      {"peaceful": 1.0, "calm": 0.7, "chill": 0.5},
    "aggressive":    {"aggressive": 1.0, "intense": 0.7},
    "dreamy":        {"dreamy": 1.0, "ethereal": 0.7},
    "party":         {"party": 1.0, "club": 0.6, "dance": 0.5},
    "summer":        {"summer": 1.0, "beach": 0.4},
    "sentimental":   {"nostalgic": 0.8, "sentimental": 0.8},
    "emotional":     {"emotional": 1.0, "passionate": 0.6},
    "uplifting":     {"uplifting": 1.0, "euphoric": 0.5},
    "introspective": {"introspective": 1.0},
    "chill":         {"chill": 1.0, "calm": 0.6, "relaxed": 0.5},
    "intense":       {"intense": 1.0, "dark": 0.4},
    "positive":      {"happy": 0.7, "upbeat": 0.6, "feel_good": 0.6},
    "hopeful":       {"uplifting": 0.7, "nostalgic": 0.4},
    "feel good":     {"feel_good": 1.0, "happy": 0.7, "upbeat": 0.5},
    "euphoric":      {"euphoric": 1.0, "happy": 0.5},
    "nightlife":     {"night": 0.8, "club": 0.7, "party": 0.5},
    "workout":       {"workout": 1.0, "energetic": 0.7, "high_energy": 0.6},
    "driving":       {"driving": 1.0, "night": 0.4},
    "road trip":     {"driving": 0.7, "summer": 0.5},
    "relaxation":    {"relaxed": 1.0, "calm": 0.7, "chill": 0.6},
    "melancholy":    {"melancholic": 1.0, "sad": 0.5},
    "powerful":      {"intense": 0.8, "energetic": 0.6, "epic": 0.5},
    "sexy":          {"sensual": 0.8, "romantic": 0.5},
    "rebellious":    {"aggressive": 0.6, "intense": 0.5},
    "nostalgic":     {"nostalgic": 1.0},
    "lively":        {"energetic": 0.8, "upbeat": 0.7, "happy": 0.5},
}


# ── Rate limiter ───────────────────────────────────────────────────────────────

_RATE_GAP = 0.35
_last_request_time: float = 0.0


def _rate_limit() -> None:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _RATE_GAP:
        time.sleep(_RATE_GAP - elapsed)
    _last_request_time = time.monotonic()


# ── HTTP ───────────────────────────────────────────────────────────────────────

def _get(path: str) -> dict | None:
    """
    Single AudioDB API call.

    Returns:
      - parsed JSON dict on success
      - {} on HTTP error (cached as "confirmed no data")
      - None on network/timeout failure (not cached, will retry)
    """
    _rate_limit()
    url = BASE_URL + path
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Vibesort/1.0 (github.com/PapaKoftes/VibeSort)"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except urllib.error.HTTPError as _he:
        # 404 = AudioDB confirmed not found — safe to cache as empty.
        # 429 / 403 / 5xx = transient — do NOT cache; retry next scan.
        return {} if _he.code == 404 else None
    except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
        return None     # network failure — don't cache, retry next scan


# ── Cache ──────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                d.setdefault("artists", {})
                d.setdefault("tracks",  {})
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


# ── Tag helpers ────────────────────────────────────────────────────────────────

def _mood_to_tags(mood_str: str | None) -> dict[str, float]:
    """Map an AudioDB mood string to our weighted tag dict."""
    if not mood_str:
        return {}
    key = mood_str.lower().strip()
    if key in _MOOD_TAGS:
        return dict(_MOOD_TAGS[key])
    # Unknown mood: pass through as a single lowercased tag
    safe = key.replace(" ", "_").replace("-", "_")
    return {safe: 0.6} if safe else {}


def _genre_str_to_list(s: str | None) -> list[str]:
    """
    Convert a single AudioDB genre/style string to a cleaned list.
    AudioDB uses a single string; some have "/" separators.
    """
    if not s:
        return []
    parts = [p.strip().lower() for p in s.replace("/", ",").split(",")]
    return [p for p in parts if p and len(p) > 1]


# ── Artist enrichment ─────────────────────────────────────────────────────────

def get_artist_data(name: str, cache: dict | None = None) -> dict:
    """
    Fetch genres AND mood tags for an artist from TheAudioDB in a single API call.

    Returns {"genres": [str, ...], "mood_tags": {tag: weight}}.
    Both fields are empty if the artist is not found or on network error.

    Uses a single cache key "data|<name>" to avoid duplicate API calls.
    """
    key = f"data|{name.lower().strip()}"
    if cache is not None:
        entry = cache.get("artists", {}).get(key)
        if entry is not None:
            return entry if isinstance(entry, dict) else {"genres": [], "mood_tags": {}}

    hit = _get(f"search.php?s={urllib.parse.quote(name)}")
    if hit is None:
        return {"genres": [], "mood_tags": {}}   # transient — don't cache

    artists = (hit or {}).get("artists") or []
    if not artists:
        result = {"genres": [], "mood_tags": {}}
        if cache is not None:
            cache.setdefault("artists", {})[key] = result
        return result

    a = artists[0]

    # Genres
    genres: list[str] = []
    for field in ("strGenre", "strStyle"):
        genres.extend(_genre_str_to_list(a.get(field)))
    genres = list(dict.fromkeys(genres))

    # Mood tags — only from strMood (editorial mood labels).
    # strStyle holds genre/style labels ("urban", "r&b", "rock") which already feed
    # into genres above; adding them here causes false substring matches in tag_score.
    tags: dict[str, float] = {}
    for t, w in _mood_to_tags(a.get("strMood")).items():
        tags[t] = max(tags.get(t, 0.0), w)

    result = {"genres": genres, "mood_tags": tags}
    if cache is not None:
        cache.setdefault("artists", {})[key] = result
    return result


def get_artist_genres(name: str, cache: dict | None = None) -> list[str]:
    """Fetch genre list for an artist. Wrapper around get_artist_data."""
    return get_artist_data(name, cache=cache).get("genres", [])


def get_artist_mood_tags(name: str, cache: dict | None = None) -> dict[str, float]:
    """Fetch mood tags for an artist. Wrapper around get_artist_data."""
    return get_artist_data(name, cache=cache).get("mood_tags", {})


# ── Track enrichment ──────────────────────────────────────────────────────────

def get_track_mood_tags(
    artist: str, title: str, cache: dict | None = None
) -> dict[str, float]:
    """
    Fetch mood/genre/theme tags for a track from TheAudioDB.
    Returns {tag: weight}.
    """
    key = f"{artist.lower().strip()}::{title.lower().strip()}"
    if cache is not None:
        entry = cache.get("tracks", {}).get(key)
        if entry is not None:
            return entry if isinstance(entry, dict) else {}

    q = f"s={urllib.parse.quote(artist)}&t={urllib.parse.quote(title)}"
    hit = _get(f"searchtrack.php?{q}")
    if hit is None:
        return {}

    items = (hit or {}).get("track") or []
    if not items:
        if cache is not None:
            cache.setdefault("tracks", {})[key] = {}
        return {}

    t = items[0]
    tags: dict[str, float] = {}

    # Mood (highest weight — direct signal)
    for tg, w in _mood_to_tags(t.get("strMood")).items():
        tags[tg] = max(tags.get(tg, 0.0), w)

    # Theme (medium weight)
    for tg, w in _mood_to_tags(t.get("strTheme")).items():
        tags[tg] = max(tags.get(tg, 0.0), w * 0.7)

    # Genre as tag context (lower weight)
    for genre in _genre_str_to_list(t.get("strGenre")):
        safe = genre.replace(" ", "_").replace("-", "_")
        tags[safe] = max(tags.get(safe, 0.0), 0.4)

    result = tags if tags else {}
    if cache is not None:
        cache.setdefault("tracks", {})[key] = result
    return result


# ── Library enrichment ────────────────────────────────────────────────────────

def enrich_library(
    all_tracks: list[dict],
    artist_freq: dict[str, tuple[str, int]],
    existing_genres: dict | None = None,
    existing_tags: dict | None = None,
    max_artists: int = 150,
    max_tracks: int | None = None,
    progress_fn=None,
) -> tuple[dict[str, list[str]], dict[str, dict[str, float]]]:
    """
    Single-pass AudioDB enrichment. One API call per artist, not three.

    For each artist (sorted by library frequency, capped at max_artists):
      - 1 API call → genres + mood tags together (get_artist_data)
      - Genres go into artist_genres result
      - Mood tags are broadcast to all tracks by that artist

    Then for tracks still missing tags (no cap when max_tracks is None):
      - 1 API call per track → track-level mood/genre tags
      - Cache is permanent so previously-fetched tracks cost 0 API calls.

    Returns:
      (artist_genres_result, track_tags_result)
      artist_genres_result: {artist_id: [genre_str, ...]}
      track_tags_result:    {spotify_uri: {tag: weight}}
    """
    cache = _load_cache()
    existing_g = existing_genres or {}
    existing_t = existing_tags or {}

    # ── Pass 1: Artist-level (genres + mood, one call each) ──────────────────
    candidates = sorted(
        [(aid, name, cnt) for aid, (name, cnt) in artist_freq.items()],
        key=lambda x: -x[2],
    )[:max_artists]

    artist_genres_result: dict[str, list[str]] = {}
    artist_mood_result: dict[str, dict[str, float]] = {}
    total = len(candidates)

    for i, (aid, name, _) in enumerate(candidates):
        if i % 25 == 0 and progress_fn:
            progress_fn(f"AudioDB artists {i}/{total}")
        data = get_artist_data(name, cache=cache)
        if data.get("genres") and not existing_g.get(aid):
            artist_genres_result[aid] = data["genres"]
        if data.get("mood_tags"):
            artist_mood_result[aid] = data["mood_tags"]

    # ── Broadcast artist mood tags to all their tracks ────────────────────────
    track_tags_result: dict[str, dict[str, float]] = {}
    for track in all_tracks:
        uri = track.get("uri", "")
        if not uri:
            continue
        for a in (track.get("artists") or []):
            aid = a.get("id", "") if isinstance(a, dict) else ""
            artist_mood = artist_mood_result.get(aid)
            if artist_mood:
                if uri not in existing_t:
                    track_tags_result[uri] = dict(artist_mood)
                else:
                    # Artist mood is lower-priority — only add missing keys
                    for tg, tw in artist_mood.items():
                        if tg not in existing_t[uri] and tg not in track_tags_result.get(uri, {}):
                            track_tags_result.setdefault(uri, {})[tg] = tw
                break

    # ── Pass 2: Track-level tags for top tracks still missing signal ──────────
    # Only run if we haven't already gotten signal from artist mood broadcast
    _all_candidates = sorted(
        [
            t for t in all_tracks
            if t.get("uri")
            and t["uri"] not in existing_t
            and t["uri"] not in track_tags_result
        ],
        key=lambda t: -t.get("popularity", 0),
    )
    # max_tracks=None → no cap; cache is permanent so re-runs cost 0 API calls.
    track_candidates = _all_candidates if max_tracks is None else _all_candidates[:max_tracks]

    for i, track in enumerate(track_candidates):
        uri = track.get("uri", "")
        if not uri:
            continue
        if i % 25 == 0 and progress_fn:
            progress_fn(f"AudioDB tracks {i}/{len(track_candidates)}")
        artists = track.get("artists") or []
        artist_name = next(
            (a["name"] for a in artists if isinstance(a, dict) and a.get("name")), ""
        )
        title = track.get("name", "")
        if not artist_name or not title:
            continue
        tags = get_track_mood_tags(artist_name, title, cache=cache)
        if tags:
            track_tags_result[uri] = tags

    _save_cache(cache)
    return artist_genres_result, track_tags_result


# ── Keep old individual functions as thin wrappers for any external callers ───

def enrich_artists(
    artist_freq: dict[str, tuple[str, int]],
    existing_genres: dict | None = None,
    max_artists: int = 150,
    progress_fn=None,
) -> dict[str, list[str]]:
    """Thin wrapper — prefer enrich_library for new code."""
    cache = _load_cache()
    existing = existing_genres or {}
    candidates = sorted(
        [(aid, name, cnt) for aid, (name, cnt) in artist_freq.items() if not existing.get(aid)],
        key=lambda x: -x[2],
    )[:max_artists]
    result: dict[str, list[str]] = {}
    for i, (aid, name, _) in enumerate(candidates):
        if i % 25 == 0 and progress_fn:
            progress_fn(f"AudioDB artists {i}/{len(candidates)}")
        genres = get_artist_genres(name, cache=cache)
        if genres:
            result[aid] = genres
    _save_cache(cache)
    return result


# ── Cache stats ───────────────────────────────────────────────────────────────

def cache_stats() -> dict:
    cache = _load_cache()
    return {
        "artists_cached": len(cache.get("artists", {})),
        "tracks_cached":  len(cache.get("tracks", {})),
    }
