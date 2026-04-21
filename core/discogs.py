"""
discogs.py — Discogs sub-genre and style enrichment.

Discogs is a community-maintained music database with highly granular
sub-genre/style classifications at the release level. Unlike Deezer which
gives broad categories ("Rap/Hip Hop"), Discogs gives precise styles:
  Kendrick Lamar → Conscious, Trap, Jazzy Hip-Hop, Neo Soul
  Tame Impala    → Psychedelic Rock, Synth-pop, Indie Rock
  The Weeknd     → Contemporary R&B, Synth-pop, Synthwave
  Travis Scott   → Trap, Cloud Rap, Psychedelic

These feed directly into:
  1. Macro genre placement (via genre_map)
  2. Mood tag vocabulary (same weight system as AudioDB)

API: https://api.discogs.com/database/search
Rate: 25 req/min unauthenticated, 60 req/min with a free Discogs token.
      Set DISCOGS_TOKEN in .env for the higher rate.
Cache: outputs/.discogs_cache.json
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".discogs_cache.json")

# Rate limiting: unauthenticated = 25/min, authenticated = 60/min
_UNAUTH_DELAY = 2.5   # seconds between calls without a token
_AUTH_DELAY   = 1.1   # seconds with a token

_token: str = ""   # set by enrich_library via DISCOGS_TOKEN config

# ── Style → mood tag mapping ──────────────────────────────────────────────────
# Maps lowercase Discogs style strings to {mood_tag: weight}.
# Same vocabulary as AudioDB mood_tags / packs.json expected_tags.

_STYLE_MOOD: dict[str, dict[str, float]] = {
    # ── Hip-hop ──
    "trap":               {"dark": 0.5, "energetic": 0.6},
    "cloud rap":          {"dark": 0.7, "introspective": 0.6, "chill": 0.4},
    "hardcore hip-hop":   {"aggressive": 0.9, "intense": 0.7, "angry": 0.6},
    "conscious":          {"introspective": 0.8, "authentic": 0.7},
    "jazzy hip-hop":      {"chill": 0.7, "introspective": 0.5, "atmospheric": 0.4},
    "gangsta rap":        {"aggressive": 0.8, "dark": 0.7, "gritty": 0.7},
    "crunk":              {"energetic": 0.9, "party": 0.7, "aggressive": 0.5},
    "hyphy":              {"energetic": 0.9, "party": 0.7, "fun": 0.6},
    "g-funk":             {"chill": 0.7, "dark": 0.4},
    "horrorcore":         {"dark": 1.0, "aggressive": 0.7},
    "drill":              {"dark": 0.8, "aggressive": 0.7, "gritty": 0.8},
    "grime":              {"intense": 0.7, "aggressive": 0.6, "energetic": 0.6},
    "lo-fi hip-hop":      {"chill": 0.9, "introspective": 0.6},
    "boom bap":           {"introspective": 0.5, "authentic": 0.6, "chill": 0.4},
    "phonk":              {"dark": 0.8, "energetic": 0.7, "aggressive": 0.5},
    "emo rap":            {"sad": 0.8, "introspective": 0.7, "emotional": 0.7},
    "melodic rap":        {"sad": 0.5, "emotional": 0.5, "introspective": 0.4},
    # ── Electronic ──
    "synthwave":          {"dark": 0.5, "electronic": 0.8, "nostalgic": 0.7},
    "darksynth":          {"dark": 0.9, "electronic": 0.8, "intense": 0.6},
    "synth-pop":          {"electronic": 0.7, "energetic": 0.5, "nostalgic": 0.4},
    "ambient":            {"ambient": 1.0, "atmospheric": 0.8, "chill": 0.6},
    "dark ambient":       {"dark": 0.9, "atmospheric": 0.9, "ambient": 1.0},
    "trip-hop":           {"dark": 0.6, "introspective": 0.7, "chill": 0.7},
    "downtempo":          {"chill": 0.8, "introspective": 0.5, "ambient": 0.5},
    "chillout":           {"chill": 0.9, "peaceful": 0.6},
    "lo-fi":              {"chill": 0.9, "introspective": 0.6},
    "acid house":         {"energetic": 0.9, "party": 0.8, "electronic": 0.9},
    "deep house":         {"chill": 0.7, "electronic": 0.8, "sensual": 0.5},
    "progressive house":  {"energetic": 0.7, "electronic": 0.8, "euphoric": 0.5},
    "techno":             {"energetic": 0.8, "electronic": 0.9, "dark": 0.4},
    "industrial":         {"dark": 0.8, "intense": 0.8, "aggressive": 0.6},
    "noise":              {"intense": 0.9, "dark": 0.7},
    "edm":                {"energetic": 0.9, "party": 0.8, "electronic": 0.9},
    "drum n bass":        {"energetic": 0.9, "electronic": 0.8},
    "dubstep":            {"intense": 0.8, "energetic": 0.8, "dark": 0.4},
    "glitch":             {"chaotic": 0.7, "electronic": 0.8},
    "hyperpop":           {"chaotic": 0.8, "energetic": 0.9, "hype": 0.7},
    "electropop":         {"energetic": 0.7, "electronic": 0.6, "upbeat": 0.5},
    "dance-pop":          {"energetic": 0.8, "party": 0.7, "happy": 0.5},
    # ── Rock ──
    "grunge":             {"dark": 0.7, "sad": 0.4, "intense": 0.6, "raw": 0.6},
    "shoegaze":           {"dreamy": 0.9, "ethereal": 0.9, "atmospheric": 0.8},
    "dream pop":          {"dreamy": 0.9, "ethereal": 0.7, "romantic": 0.5},
    "post-rock":          {"atmospheric": 0.9, "introspective": 0.7, "cinematic": 0.8},
    "psychedelic rock":   {"trippy": 0.9, "atmospheric": 0.7, "introspective": 0.5},
    "indie rock":         {"introspective": 0.5, "authentic": 0.5},
    "alt-pop":            {"introspective": 0.4, "emotional": 0.4},
    "post-punk":          {"dark": 0.7, "introspective": 0.6, "cold": 0.5},
    "gothic rock":        {"dark": 0.9, "atmospheric": 0.7, "melancholic": 0.7},
    "darkwave":           {"dark": 0.9, "cold": 0.8, "atmospheric": 0.7},
    "emo":                {"sad": 0.7, "emotional": 0.8, "intense": 0.5, "raw": 0.6},
    "pop punk":           {"energetic": 0.7, "fun": 0.5, "emotional": 0.5},
    "punk":               {"energetic": 0.8, "aggressive": 0.6, "raw": 0.7},
    "hardcore":           {"aggressive": 0.9, "intense": 0.8, "energetic": 0.8},
    "alternative rock":   {"introspective": 0.4, "authentic": 0.4},
    "britpop":            {"fun": 0.5, "upbeat": 0.4},
    "art rock":           {"introspective": 0.6, "atmospheric": 0.5},
    # ── Metal ──
    "heavy metal":        {"intense": 0.9, "aggressive": 0.8, "energetic": 0.8},
    "thrash":             {"aggressive": 1.0, "intense": 0.9, "energetic": 0.9},
    "speed metal":        {"energetic": 1.0, "intense": 0.9, "aggressive": 0.8},
    "death metal":        {"dark": 0.9, "aggressive": 1.0, "intense": 0.9},
    "doom metal":         {"dark": 0.9, "heavy": 0.9, "sad": 0.5, "melancholic": 0.6},
    "black metal":        {"dark": 1.0, "aggressive": 0.8, "atmospheric": 0.6},
    "metalcore":          {"aggressive": 0.8, "intense": 0.8, "emotional": 0.5},
    "deathcore":          {"aggressive": 1.0, "dark": 0.8, "intense": 0.9},
    "nu-metal":           {"aggressive": 0.7, "intense": 0.7, "angry": 0.6},
    "symphonic metal":    {"cinematic": 0.7, "atmospheric": 0.6, "intense": 0.6},
    "folk metal":         {"energetic": 0.6, "fun": 0.4},
    "progressive metal":  {"cinematic": 0.6, "introspective": 0.5, "intense": 0.6},
    "stoner rock":        {"heavy": 0.7, "chill": 0.4, "dark": 0.4},
    # ── R&B / Soul ──
    "contemporary r&b":   {"soulful": 0.7, "love": 0.5, "chill": 0.4, "sensual": 0.5},
    "neo soul":           {"soulful": 0.9, "introspective": 0.6, "love": 0.6},
    "quiet storm":        {"romantic": 0.9, "love": 0.8, "chill": 0.7},
    "funk":               {"fun": 0.7, "energetic": 0.6, "dance": 0.7},
    "soul":               {"soulful": 0.9, "emotional": 0.6, "love": 0.5},
    "gospel":             {"uplifting": 0.9, "spiritual": 0.9, "powerful": 0.7},
    # ── Jazz ──
    "jazz-funk":          {"fun": 0.6, "chill": 0.5, "energetic": 0.5},
    "cool jazz":          {"chill": 0.9, "introspective": 0.6},
    "bossa nova":         {"chill": 0.8, "romantic": 0.6, "warm": 0.6},
    "free jazz":          {"chaotic": 0.5, "introspective": 0.6},
    # ── Country / Folk ──
    "outlaw country":     {"authentic": 0.8, "raw": 0.6, "introspective": 0.5},
    "americana":          {"introspective": 0.6, "authentic": 0.7, "melancholic": 0.4},
    "bluegrass":          {"energetic": 0.5, "fun": 0.5, "authentic": 0.6},
    # ── Latin ──
    "reggaeton":          {"energetic": 0.9, "dance": 0.9, "party": 0.8},
    "salsa":              {"energetic": 0.9, "dance": 0.9, "fun": 0.8},
    "bossa nova":         {"chill": 0.8, "romantic": 0.6},
    # ── Classical ──
    "modern classical":   {"atmospheric": 0.7, "cinematic": 0.6, "introspective": 0.6},
    "ambient classical":  {"ambient": 0.8, "atmospheric": 0.8, "peaceful": 0.6},
}


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"artists": {}}


def _save_cache(cache: dict) -> None:
    try:
        from core.cache_io import atomic_write_json
        atomic_write_json(CACHE_PATH, cache, separators=(",", ":"))
    except Exception:
        pass


# ── API helpers ───────────────────────────────────────────────────────────────

_last_call: float = 0.0


def _get(path: str) -> dict | None:
    """Make a rate-limited GET to api.discogs.com. Returns None on transient error."""
    global _last_call
    delay = _AUTH_DELAY if _token else _UNAUTH_DELAY
    gap = time.time() - _last_call
    if gap < delay:
        time.sleep(delay - gap)

    headers = {"User-Agent": "Vibesort/1.0 +https://github.com/vibesort"}
    if _token:
        headers["Authorization"] = f"Discogs token={_token}"

    url = f"https://api.discogs.com/{path}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            _last_call = time.time()
            return json.loads(r.read())
    except urllib.error.HTTPError as he:
        _last_call = time.time()
        # 404 = Discogs confirmed not found; anything else = transient, retry later
        return {} if he.code == 404 else None
    except Exception:
        _last_call = time.time()
        return None


def _styles_to_tags(styles: list[str]) -> dict[str, float]:
    """Translate a list of Discogs style strings to a weighted mood tag dict."""
    tags: dict[str, float] = {}
    for style in styles:
        mapping = _STYLE_MOOD.get(style.lower())
        if mapping:
            for tag, weight in mapping.items():
                tags[tag] = max(tags.get(tag, 0.0), weight)
    return tags


# ── Artist lookup ─────────────────────────────────────────────────────────────

def get_artist_styles(
    artist_name: str,
    cache: dict | None = None,
    max_releases: int = 8,
) -> dict:
    """
    Fetch the most common Discogs styles/genres for an artist.

    Returns {"styles": [...], "genres": [...], "mood_tags": {tag: weight}}.
    Styles are Discogs's precise sub-genre labels; mood_tags are the
    translated weight dict for scorer consumption.
    """
    key = artist_name.lower().strip()
    if cache is not None:
        entry = cache.get("artists", {}).get(key)
        if entry is not None:
            return entry if isinstance(entry, dict) else {"styles": [], "genres": [], "mood_tags": {}}

    # Search for releases by this artist
    q = urllib.parse.quote(key)
    data = _get(f"database/search?type=release&artist={q}&per_page={max_releases}")
    if data is None:
        return {"styles": [], "genres": [], "mood_tags": {}}  # transient — don't cache

    style_counts: Counter = Counter()
    genre_counts: Counter = Counter()
    for result in (data or {}).get("results", []):
        for s in result.get("style", []):
            style_counts[s] += 1
        for g in result.get("genre", []):
            genre_counts[g] += 1

    # Take most common (weighted by frequency across releases)
    top_styles = [s for s, _ in style_counts.most_common(6)]
    top_genres = [g for g, _ in genre_counts.most_common(3)]
    mood_tags  = _styles_to_tags(top_styles)

    result_dict = {"styles": top_styles, "genres": top_genres, "mood_tags": mood_tags}

    if cache is not None:
        cache.setdefault("artists", {})[key] = result_dict
        _save_cache(cache)

    return result_dict


# ── Library enrichment ────────────────────────────────────────────────────────

def enrich_library(
    all_tracks: list[dict],
    artist_freq: dict[str, tuple[str, int]],
    existing_genres: dict | None = None,
    existing_tags: dict | None = None,
    discogs_token: str = "",
    max_artists: int = 120,
    progress_fn=None,
) -> tuple[dict[str, list[str]], dict[str, dict[str, float]]]:
    """
    Enrich the library with Discogs sub-genre styles and mood tags.

    For each top artist (by track frequency):
      - 1 API call → styles + genre list + mood tag translation
      - Styles stored as additional genres (supplements Deezer)
      - Mood tags broadcast to all tracks by that artist

    Returns:
      (artist_genres_result, track_tags_result)
    """
    global _token
    _token = discogs_token.strip()

    cache = _load_cache()
    existing_g = existing_genres or {}
    existing_t = existing_tags or {}

    # Sort artists by library frequency (most tracks first)
    candidates = sorted(
        [(aid, name, cnt) for aid, (name, cnt) in artist_freq.items()],
        key=lambda x: -x[2],
    )[:max_artists]

    artist_styles_result: dict[str, dict] = {}
    total = len(candidates)

    for i, (aid, name, _) in enumerate(candidates):
        if i % 20 == 0 and progress_fn:
            progress_fn(f"Discogs styles {i}/{total}")
        data = get_artist_styles(name, cache=cache)
        if data.get("styles") or data.get("genres"):
            artist_styles_result[aid] = data

    # Build output dicts
    artist_genres_result: dict[str, list[str]] = {}
    track_tags_result:    dict[str, dict[str, float]] = {}

    for aid, data in artist_styles_result.items():
        # Add Discogs styles as supplemental genre strings
        # (to_macro will map them via macro_genres.json rules)
        new_genres = data.get("styles", []) + data.get("genres", [])
        if new_genres:
            existing = list(existing_g.get(aid, []))
            for g in new_genres:
                if g not in existing:
                    existing.append(g)
            artist_genres_result[aid] = existing

    # Broadcast mood tags to all tracks
    for track in all_tracks:
        uri = track.get("uri", "")
        if not uri:
            continue
        for a in (track.get("artists") or []):
            aid = a.get("id", "") if isinstance(a, dict) else ""
            data = artist_styles_result.get(aid)
            if not data:
                continue
            mood_tags = data.get("mood_tags", {})
            if not mood_tags:
                break
            if uri not in existing_t and uri not in track_tags_result:
                track_tags_result[uri] = dict(mood_tags)
            else:
                # Merge — style tags are lower priority than direct mood data
                base = dict(track_tags_result.get(uri) or existing_t.get(uri, {}))
                for tag, weight in mood_tags.items():
                    if tag not in base:
                        base[tag] = weight
                track_tags_result[uri] = base
            break

    return artist_genres_result, track_tags_result
