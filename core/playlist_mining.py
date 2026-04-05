"""
playlist_mining.py — Extract human meaning from Spotify playlist names.

Strategy (search-based):

For each mood, we search Spotify for public playlists using seed phrases from
packs.json.  Any user track that appears in those playlists gets tags derived
from the playlist name.  Tag weight is proportional to how many playlists the
track appears in and the playlist's relevance.

Bonus: PUBLIC PLAYLIST FINDER
  After mining we record, per mood, the top public playlists ranked by how many
  of the user's tracks they contain.  These surface on the Vibes page as
  "Playlists you'd fit right into."

Results are cached to <project_root>/outputs/.mining_cache.json (7-day TTL).
Delete the file to force a refresh.
"""

import re
import json
import os
import math
import time
import collections
import spotipy
from core.anchors import get_anchor_ids
from core.profile import collapse_tags as _collapse_tags

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".mining_cache.json")
CACHE_TTL_DAYS = 7

# Stopwords to remove when extracting tags from playlist names
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "be", "been", "my",
    "your", "our", "their", "its", "this", "that", "these", "those", "it",
    "playlist", "music", "songs", "tracks", "mix", "hits", "vol",
    "best", "top", "new", "i", "you", "we", "they", "he", "she",
}

COMPOUND_TAGS = [
    "late night", "night drive", "late night drive", "dark phonk",
    "gym rage", "deep focus", "chill vibes", "sad songs", "feel good",
    "good vibes", "golden hour", "after hours", "lo fi", "lo-fi",
    "study music", "work out", "warm up", "slow burn", "broken heart",
    "overthinking", "night time", "drive home", "summer vibes",
    "dark energy", "villain arc", "hype up", "turn up", "come down",
    "road trip", "open road", "night drive", "sad hours", "soft hours",
    "early morning", "late night", "feel good friday", "after party",
    "smoke session", "hard reset", "signal lost", "deep work",
]

# ── Phrase boost weights ───────────────────────────────────────────────────────
# Compound tags that are highly diagnostic of a specific mood carry more signal
# than single generic words.  When a playlist name contains one of these phrases
# the tag gets this weight multiplier instead of the default 1.0.
#
# Scale: 1.0 = normal word, 2.0 = strong signal, 3.0 = diagnostic phrase.
PHRASE_BOOST: dict[str, float] = {
    # ── Night / drive
    "late_night_drive": 3.0,
    "night_drive":      2.5,
    "late_night":       2.0,
    "drive_home":       2.0,
    "midnight_drive":   2.5,
    "road_trip":        2.0,
    "open_road":        2.5,
    # ── Mood / feeling
    "sad_songs":        2.5,
    "sad_hours":        2.5,
    "feel_good":        2.0,
    "feel_good_friday": 2.0,
    "broken_heart":     2.5,
    "soft_hours":       2.5,
    "chill_vibes":      2.0,
    "good_vibes":       1.8,
    "dark_energy":      2.5,
    "overthinking":     2.5,
    "slow_burn":        2.0,
    "villain_arc":      3.0,
    "hype_up":          2.0,
    "after_hours":      2.0,
    "after_party":      2.0,
    "signal_lost":      2.0,
    "summer_vibes":     2.0,
    "night_time":       1.5,
    # ── Activity / context
    "dark_phonk":       3.0,
    "gym_rage":         3.0,
    "deep_focus":       2.5,
    "study_music":      2.5,
    "deep_work":        2.5,
    "work_out":         2.0,
    "warm_up":          1.5,
    "smoke_session":    2.5,
    "hard_reset":       2.5,
    "golden_hour":      2.5,
    "lo_fi":            2.2,
    "early_morning":    2.0,
    "turn_up":          1.8,
    "come_down":        2.0,
    "rainy_day":        2.2,
    "amapiano":         2.3,
    "anime":            2.0,
    "meditation":       2.0,
    "disco":            2.0,
    "techno":           2.0,
    "metal":            2.0,
    "punk":             2.0,
    "chillhop":         2.0,
    "classical":        1.8,
    "vaporwave":        2.2,
    "jpop":             2.0,
}

# ── Tag normalisation groups ───────────────────────────────────────────────────
# Many playlists use synonymous words that fragment meaning.
# "night" / "nights" / "midnight" / "late" all refer to the same concept.
# We map every VARIANT → CANONICAL so the scorer sees one unified signal.
#
# Mapping is applied AFTER compound-tag extraction so "late_night" is already
# captured as a boosted compound before its words are normalised individually.
TAG_GROUPS: dict[str, list[str]] = {
    # canonical   → [variants that collapse into it]
    "night":    ["nights", "nighttime", "midnight", "nocturnal", "late"],
    "drive":    ["driving", "driver", "cruise", "cruising", "road_trip"],
    "gym":      ["workout", "lifting", "training", "exercise", "fitness", "work_out"],
    "chill":    ["chilled", "chilling", "relax", "relaxed", "mellow", "laid_back"],
    "sad":      ["sadness", "crying", "cry", "tears", "heartbreak", "emotional"],
    "hype":     ["hyped", "fire", "lit", "turnt", "banger", "heat"],
    "dark":     ["darkness", "sinister", "eerie", "shadow", "noir", "shadowy"],
    "party":    ["parties", "clubbing", "rave", "festival", "dancefloor"],
    "love":     ["romance", "romantic", "lover", "crush", "affection"],
    "anger":    ["angry", "rage", "mad", "furious", "fury"],
    "focus":    ["studying", "concentration", "deep_work", "study_music", "work"],
    "phonk":    ["dark_phonk", "drift_phonk", "phonk_season"],
    "summer":   ["summertime", "sunshine", "sunny", "warm", "warmth"],
    "sleep":    ["sleeping", "sleepy", "ambient", "rest", "resting"],
    "morning":  ["sunrise", "dawn", "wakeup", "early_morning"],
    "workout":  ["preworkout", "pre_workout", "beast_mode", "gains", "sweat"],
}

# Build reverse lookup: variant → canonical
_VARIANT_TO_CANONICAL: dict[str, str] = {}
for _canonical, _variants in TAG_GROUPS.items():
    for _variant in _variants:
        _VARIANT_TO_CANONICAL[_variant] = _canonical


def normalize_tag(tag: str) -> str:
    """Return the canonical form of a tag, collapsing synonyms."""
    return _VARIANT_TO_CANONICAL.get(tag, tag)


# ── Semantic tag expansion ─────────────────────────────────────────────────────
# Compound/contextual tags imply richer meaning than their words alone.
# When a track has one of these tags, we automatically add the implied
# semantic tags at a reduced weight (SEMANTIC_WEIGHT × original weight).
# This gives the scorer more dimensions to match on without requiring
# every playlist to explicitly use those exact tag words.
#
# Example:
#   "late_night_drive" (w=1.0) → also adds "introspective" (w=0.5),
#   "dark" (w=0.5), "drive" (w=0.5), "night" (w=0.5)
#
# The expansion weight is deliberately low so it supplements, not replaces,
# real evidence.  A track with explicit "dark" tag still beats one that only
# inherited it via semantic expansion.

SEMANTIC_WEIGHT = 0.50   # weight of implied semantic tags vs source tag
BASIC_WEIGHT    = 0.35   # weight for simple-tag expansions (weaker than compound)

# ── Basic tag expansion (simple / atomic tags → implied concepts) ─────────────
# SEMANTIC_MAP covers compound phrases ("late_night_drive" → many concepts).
# BASIC_MAP handles atomic genre/vibe words — they also imply related dimensions
# but more loosely, so they get a lighter weight (BASIC_WEIGHT = 0.35 vs 0.50).
#
# This fills the gap where a track was tagged from playlists named simply
# "Phonk Playlist" or "Ambient Study" — single words that still carry meaning.
#
# Rule: only add implied tags that are clearly *derived from* the source tag,
# not everything loosely related.  The expansion should add signal, not noise.
BASIC_MAP: dict[str, list[str]] = {
    # ── Genre tags → implied mood/context
    "ambient":      ["chill", "focus", "sleep", "introspective"],
    "phonk":        ["dark", "drive", "night", "anger"],
    "drill":        ["dark", "anger", "night", "street"],
    "lofi":         ["chill", "focus", "study", "night"],
    "jazz":         ["chill", "night", "sophisticated"],
    "blues":        ["sad", "introspective", "chill"],
    "metal":        ["anger", "hype", "dark"],
    "acoustic":     ["chill", "introspective", "sad", "soft"],
    "country":      ["summer", "drive", "nostalgic"],
    "gospel":       ["worship", "uplift", "spiritual"],
    "trap":         ["dark", "hype", "night"],
    "rnb":          ["chill", "love", "night", "smooth"],
    "soul":         ["introspective", "love", "warm"],
    "indie":        ["introspective", "chill", "authentic"],
    "electronic":   ["hype", "night", "energy"],
    "classical":    ["focus", "ambient", "introspective"],
    "piano":        ["introspective", "chill", "sad", "ambient"],
    "guitar":       ["chill", "acoustic", "introspective"],

    # ── Mood/vibe tags → implied context
    "dark":         ["night", "introspective"],
    "chill":        ["relax", "soft", "gentle"],
    "hype":         ["energy", "pump"],
    "sad":          ["introspective", "slow"],
    "happy":        ["energy", "summer", "bright"],
    "angry":        ["dark", "hype"],
    "nostalgic":    ["introspective", "chill", "bittersweet"],
    "romantic":     ["love", "chill", "night"],
    "motivational": ["hype", "energy", "confident"],
    "melancholic":  ["sad", "introspective", "night"],
    "peaceful":     ["chill", "ambient", "sleep"],
    "intense":      ["energy", "hype", "focus"],
    "groovy":       ["dance", "chill", "happy"],
    "sexy":         ["love", "night", "smooth"],
    "rebellious":   ["anger", "dark", "hype"],
    "spiritual":    ["introspective", "ambient", "chill"],

    # ── Activity tags → implied mood
    "study":        ["focus", "chill", "ambient"],
    "gym":          ["hype", "energy", "anger"],
    "sleep":        ["chill", "ambient", "soft"],
    "party":        ["hype", "happy", "dance"],
    "workout":      ["hype", "energy", "gym"],
    "running":      ["hype", "energy", "drive"],
    "meditation":   ["ambient", "chill", "spiritual"],
    "coffee":       ["morning", "chill", "introspective"],
    "shower":       ["happy", "chill", "morning"],
    "cooking":      ["happy", "chill", "summer"],

    # ── Time/place tags → implied mood
    "morning":      ["soft", "chill", "happy"],
    "night":        ["introspective", "dark", "chill"],
    "summer":       ["happy", "energy", "warm"],
    "winter":       ["introspective", "chill", "sad"],
    "rain":         ["sad", "introspective", "chill"],
    "drive":        ["night", "introspective", "freedom"],
    "beach":        ["happy", "summer", "chill"],
    "city":         ["night", "energy", "dark"],
    "sunset":       ["nostalgic", "chill", "warm"],
}

SEMANTIC_MAP: dict[str, list[str]] = {
    # ── Night / drive
    "late_night_drive": ["introspective", "dark", "drive", "night"],
    "night_drive":      ["dark", "drive", "night"],
    "drive_home":       ["drive", "night", "chill"],
    "open_road":        ["drive", "summer", "freedom"],
    "road_trip":        ["drive", "summer", "freedom"],

    # ── Dark / villain
    "villain_arc":      ["dark", "anger", "confident"],
    "dark_energy":      ["dark", "anger", "night"],
    "dark_phonk":       ["dark", "phonk", "anger"],
    "signal_lost":      ["dark", "ambient", "eerie"],

    # ── Energy / gym
    "gym_rage":         ["hype", "anger", "gym"],
    "hype_up":          ["hype", "party", "energy"],
    "beast_mode":       ["hype", "gym", "anger"],
    "hard_reset":       ["anger", "hype", "gym"],

    # ── Chill / soft
    "chill_vibes":      ["chill", "relax", "mellow"],
    "slow_burn":        ["chill", "dark", "introspective"],
    "smoke_session":    ["chill", "dark", "night"],
    "soft_hours":       ["chill", "love", "gentle"],
    "sunday_soft":      ["chill", "morning", "gentle"],

    # ── Sad / emotional
    "sad_songs":        ["sad", "hollow", "emotional"],
    "sad_hours":        ["sad", "night", "hollow"],
    "broken_heart":     ["sad", "love", "hollow"],
    "overthinking":     ["introspective", "sad", "night"],

    # ── Happy / positive
    "feel_good":        ["hype", "happy", "summer"],
    "golden_hour":      ["warm", "happy", "summer"],
    "summer_vibes":     ["happy", "summer", "party"],
    "good_vibes":       ["happy", "chill", "summer"],
    "feel_good_friday": ["happy", "party", "hype"],

    # ── Night / ambient / introspective
    "midnight_clarity": ["introspective", "night", "sad"],
    "deep_focus":       ["focus", "chill", "ambient"],
    "deep_work":        ["focus", "chill", "ambient"],
    "study_music":      ["focus", "chill"],
    "after_hours":      ["night", "dark", "party"],
    "after_party":      ["party", "night", "chill"],
    "late_night":       ["night", "introspective"],
}


def _apply_semantic_expansion(
    tag_weights: dict[str, float],
) -> dict[str, float]:
    """
    Return a NEW tag_weights dict with semantic expansions merged in.

    Two expansion passes — higher-weight rules never overwritten by lower:

    Pass 1 — SEMANTIC_MAP (compound/contextual phrases):
      Each matching tag adds implied tags at SEMANTIC_WEIGHT (0.50) ×
      the source tag's weight.  Compound phrases carry more semantic weight
      because they are more specific ("late_night_drive" → 4 implied dims).

    Pass 2 — BASIC_MAP (atomic genre/vibe/activity tags):
      Each matching tag adds implied tags at BASIC_WEIGHT (0.35) ×
      the source tag's weight.  Atomic tags are less specific so their
      expansion is weaker — it supplements, never dominates.

    In both passes, an implied tag is only set if it is absent or currently
    weaker.  This ensures explicit evidence always beats inferred evidence.
    """
    expanded = dict(tag_weights)

    # Pass 1: compound/contextual phrases (stronger signal)
    for tag, weight in tag_weights.items():
        implied = SEMANTIC_MAP.get(tag)
        if not implied:
            continue
        impl_weight = weight * SEMANTIC_WEIGHT
        for impl_tag in implied:
            if expanded.get(impl_tag, 0.0) < impl_weight:
                expanded[impl_tag] = impl_weight

    # Pass 2: atomic tags (weaker signal — fills gaps, doesn't dominate)
    for tag, weight in tag_weights.items():
        implied = BASIC_MAP.get(tag)
        if not implied:
            continue
        impl_weight = weight * BASIC_WEIGHT
        for impl_tag in implied:
            if expanded.get(impl_tag, 0.0) < impl_weight:
                expanded[impl_tag] = impl_weight

    return expanded


# ── Tag extraction ─────────────────────────────────────────────────────────────

def extract_tags(text: str) -> list[str]:
    """
    Extract tags from a playlist name.

    1. Compound phrases (COMPOUND_TAGS) are extracted first and underscore-joined.
    2. Remaining individual words (filtered by STOPWORDS) are extracted.
    3. Each tag is normalised to its canonical form via normalize_tag().

    Returns a deduplicated list in extraction order.
    """
    text_lower = text.lower()
    tags: list[str] = []
    for phrase in COMPOUND_TAGS:
        if phrase in text_lower:
            tags.append(normalize_tag(phrase.replace(" ", "_")))
    words = re.findall(r"[a-z]+", text_lower)
    for word in words:
        if word not in STOPWORDS and len(word) > 2:
            tags.append(normalize_tag(word))
    return list(dict.fromkeys(tags))


def _tag_weight(tag: str) -> float:
    """Return the boost multiplier for a tag.  Compound/diagnostic phrases > 1.0."""
    return PHRASE_BOOST.get(tag, 1.0)


# ── Playlist fetching ──────────────────────────────────────────────────────────

def _search_playlists(sp: spotipy.Spotify, query: str, limit: int = 10) -> list[dict]:
    """
    Search for public playlists matching a query.
    NOTE: Spotify's search API returns PlaylistSimplified objects which do NOT
    include a followers field — we accept all results and don't filter on followers.
    """
    try:
        result = sp.search(q=query, type="playlist", limit=limit)
        playlists = result.get("playlists", {}).get("items", []) or []
        return [pl for pl in playlists if pl and pl.get("id")]
    except Exception:
        return []


def _playlist_track_uris(
    sp: spotipy.Spotify,
    playlist_id: str,
    max_tracks: int = 200,
    _blocked_flag: list | None = None,
    _budget: dict | None = None,
    _batch_gap: float = 0.12,
) -> list[str]:
    """Fetch track URIs from a playlist (up to max_tracks).

    _blocked_flag: optional single-element list used as an out-param.
    If the request is 403'd, _blocked_flag[0] is set to True.
    _budget: optional {"calls": int, "max": int} — counts each playlist_items page.
    """
    try:
        uris = []
        offset = 0
        while len(uris) < max_tracks:
            if _budget is not None and _budget["calls"] >= _budget["max"]:
                break
            if _budget is not None:
                _budget["calls"] += 1
            batch = sp.playlist_items(
                playlist_id,
                limit=min(100, max_tracks - len(uris)),
                offset=offset,
                additional_types=["track"],
            )
            items = (batch or {}).get("items", []) or []
            if not items:
                break
            for item in items:
                t = item.get("track")
                if t and t.get("uri") and t["uri"].startswith("spotify:track:"):
                    uris.append(t["uri"])
            if not batch.get("next"):
                break
            offset += 100
            time.sleep(max(_batch_gap, 0.05))
        return uris
    except Exception as _exc:
        _s = str(_exc)
        if ("403" in _s or "Forbidden" in _s) and _blocked_flag is not None:
            _blocked_flag[0] = True
        return []


# ── Cache ──────────────────────────────────────────────────────────────────────

def _load_cache() -> dict | None:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        import datetime
        ts = data.get("_timestamp", "")
        if ts:
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(ts)).days
            if age > CACHE_TTL_DAYS:
                return None
        # Reject empty/broken caches (e.g. from previous failed runs)
        if not data.get("track_tags"):
            return None
        return data
    except Exception:
        return None


def _save_cache(data: dict) -> None:
    import datetime
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    data["_timestamp"] = datetime.datetime.now().isoformat()
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


# ── Owned-playlist fallback ───────────────────────────────────────────────────

def _mine_owned_playlists(
    sp: spotipy.Spotify,
    user_uris: set[str],
    *,
    max_playlist_fetches: int = 48,
    items_batch_gap: float = 0.12,
) -> dict:
    """
    Mine the current user's OWN playlists for track→tag context.

    In Spotify's Development Mode, playlist_items is blocked for 3rd-party
    playlists but works fine for playlists owned by the authenticated user.
    This gives us free mood/genre signal from names like:
      "Sad Hours", "Late Night Drive", "Gym Rage", "Chill Sundays", etc.

    The tags extracted here feed directly into scorer.tag_score(), so even
    a handful of well-named playlists yields meaningful mood detection.

    Returns the same dict shape as mine() (without "blocked" key).
    """
    # Fetch the user's own playlists (names available from list call)
    try:
        user_id = sp.current_user()["id"]
    except Exception:
        return {
            "track_tags": {}, "track_context": {},
            "tag_index": {}, "mood_fit_playlists": {},
            "blocked": False,
        }

    owned: list[dict] = []
    offset = 0
    while True:
        try:
            batch = sp.current_user_playlists(limit=50, offset=offset)
            items = batch.get("items") or []
            if not items:
                break
            for pl in items:
                if pl and pl.get("id") and pl.get("owner", {}).get("id") == user_id:
                    owned.append(pl)
            if not batch.get("next"):
                break
            offset += 50
            time.sleep(0.08)
        except Exception:
            break

    if not owned:
        print("  Own playlists         0 owned playlists found")
        return {
            "track_tags": {}, "track_context": {},
            "tag_index": {}, "mood_fit_playlists": {},
            "blocked": False,
        }

    track_context: dict = collections.defaultdict(list)
    enriched_pl = 0
    _items_blocked = [False]   # out-param: set True on first 403
    _fetch_count = 0

    for pl in owned:
        if _fetch_count >= max_playlist_fetches:
            print(f"  Own playlists         fetch cap ({max_playlist_fetches}) — stopping")
            break
        pid     = pl.get("id", "")
        pl_name = pl.get("name") or ""
        tags    = extract_tags(pl_name)
        if not tags:
            continue   # playlist name has no useful words — skip

        _fetch_count += 1
        uris = _playlist_track_uris(
            sp, pid, max_tracks=400, _blocked_flag=_items_blocked, _batch_gap=items_batch_gap,
        )
        time.sleep(max(items_batch_gap, 0.08))
        if _items_blocked[0]:
            break   # all playlist_items calls are blocked — stop early

        matched = 0
        for uri in uris:
            if uri in user_uris:
                track_context[uri].append({
                    "playlist_id": pid,
                    "playlist":    pl_name,
                    "followers":   0,
                    "mood":        None,
                    "tags":        tags,
                })
                matched += 1
        if matched:
            enriched_pl += 1

    # Build weighted track_tags (phrase boost + semantic expansion)
    track_tags: dict = {}
    tag_index: dict  = collections.defaultdict(list)

    for uri, contexts in track_context.items():
        raw_weights: dict = collections.defaultdict(float)
        for ctx in contexts:
            for tag in ctx["tags"]:
                tag_weight = _tag_weight(tag)
                tag_weight *= 3.0  # owned playlists = strong user signal
                raw_weights[tag] += tag_weight

        if raw_weights:
            # Apply semantic expansion before normalising
            expanded = _apply_semantic_expansion(dict(raw_weights))
            max_w = max(expanded.values())
            _built = {t: round(w / max_w, 4) for t, w in expanded.items()}
            _clusters = _collapse_tags(_built)
            track_tags[uri] = {**_built, **_clusters} if _clusters else _built
        for tag in track_tags.get(uri, {}):
            if uri not in tag_index[tag]:
                tag_index[tag].append(uri)

    total_tagged = sum(1 for t in track_tags.values() if t)
    if _items_blocked[0]:
        print(
            f"  Own playlists mined   [playlist_items blocked by Spotify Dev Mode "
            f"— 0 tracks tagged from {len(owned)} playlists]"
        )
    else:
        print(
            f"  Own playlists mined   {total_tagged} tracks tagged "
            f"from {enriched_pl}/{len(owned)} playlists"
        )

    return {
        "track_tags":              track_tags,
        "track_context":           {k: list(v) for k, v in track_context.items()},
        "tag_index":               dict(tag_index),
        "mood_fit_playlists":      {},
        "blocked":                 False,
        "playlist_items_blocked":  _items_blocked[0],
    }


# ── Core mining ────────────────────────────────────────────────────────────────

def mine(
    sp: spotipy.Spotify,
    user_uris: set[str],
    mood_packs: dict,
    playlists_per_seed: int = 6,
    max_tracks_per_playlist: int | None = None,
    force_refresh: bool = False,
) -> dict:
    """
    Mine public Spotify playlists for track context.

    For each mood, searches Spotify using seed_phrases from packs.json.
    Any user track found in those playlists gets tags from the playlist name.

    Returns:
      {
        "track_tags":        {uri: {tag: weight}},
        "track_context":     {uri: [{playlist_name, followers, mood, tags}]},
        "tag_index":         {tag: [uri, ...]},
        "mood_fit_playlists":{mood: [{id, name, overlap_count, followers}]},
      }
    """
    if not force_refresh:
        cached = _load_cache()
        if cached:
            print("  Playlist mining       loaded from cache")
            cached.setdefault("blocked", False)
            cached.setdefault("playlist_items_blocked", cached.get("blocked", False))
            return cached

    import config as _cfg

    _mtp = (
        max_tracks_per_playlist
        if max_tracks_per_playlist is not None
        else int(getattr(_cfg, "MINING_MAX_TRACKS_PER_PLAYLIST", 100))
    )
    _max_calls = int(getattr(_cfg, "MINING_MAX_PLAYLIST_ITEMS_CALLS", 320))
    _budget = {"calls": 0, "max": _max_calls}
    _search_delay = float(getattr(_cfg, "MINING_SEARCH_DELAY", 0.38))
    _items_gap = float(getattr(_cfg, "MINING_PLAYLIST_ITEMS_GAP", 0.14))
    _batch_gap = float(getattr(_cfg, "MINING_ITEMS_BATCH_GAP", 0.12))
    _max_seeds = int(getattr(_cfg, "MINING_MAX_SEED_PHRASES", 2))
    _max_anchors = int(getattr(_cfg, "MINING_MAX_ANCHORS_PER_MOOD", 4))
    _max_owned = int(getattr(_cfg, "MINING_MAX_OWNED_PLAYLISTS", 48))

    print("  Playlist mining       starting (owned playlists first)...")

    # ── STEP 1: Always mine owned playlists first (highest-quality signal) ────
    # User-named playlists are zero-noise ground truth.  "Late Night Drive",
    # "Gym Rage", "Chill Sundays" — these are precise, intentional mood labels.
    # Random public search playlists are supplemental, not primary.
    own = _mine_owned_playlists(
        sp,
        user_uris,
        max_playlist_fetches=_max_owned,
        items_batch_gap=_batch_gap,
    )
    owned_context: dict = own.get("track_context", {})

    # Seed the main track_context with owned-playlist data (mood=None, no bias)
    track_context: dict[str, list[dict]] = collections.defaultdict(list)
    for uri, ctxs in owned_context.items():
        for ctx in ctxs:
            track_context[uri].append(ctx)

    # ── STEP 2: Probe whether public playlist_items is accessible ─────────────
    # Spotify Dev Mode restricts playlist_items for playlists not owned by users
    # registered in the app.  Probe once before hammering all moods.
    _probe_playlists = _search_playlists(sp, "chill vibes", limit=3)
    time.sleep(_search_delay)
    _probe_blocked = False
    for _pp in _probe_playlists:
        _probe_id = _pp.get("id")
        if not _probe_id:
            continue
        try:
            if _budget["calls"] < _budget["max"]:
                _budget["calls"] += 1
            sp.playlist_items(_probe_id, limit=1, additional_types=["track"])
            time.sleep(_batch_gap)
        except Exception as _pe:
            if "403" in str(_pe) or "Forbidden" in str(_pe):
                _probe_blocked = True
        break  # only probe once

    fetched_ids: set[str] = set()   # defined here so final print is always valid
    _budget_hit = False

    if _probe_blocked:
        print("  [warn] public playlist_items blocked (Dev Mode) — "
              "using owned playlists only")
        # Still build and return from owned data collected above
    else:
        # ── STEP 3: Supplement with public search (secondary signal) ──────────
        total_moods = len(mood_packs)
        processed_moods = 0

        for mood_name, pack in mood_packs.items():
            if _budget["calls"] >= _budget["max"]:
                _budget_hit = True
                break
            processed_moods += 1
            seed_phrases = pack.get("seed_phrases", [])
            if not seed_phrases:
                seed_phrases = [mood_name.lower()]

            queries_used = seed_phrases[:_max_seeds]
            print(
                f"\r  Searching             {processed_moods}/{total_moods}: {mood_name[:30]:<30}",
                end="", flush=True,
            )

            # Prepend anchor playlists for this mood (curated, high-quality signal)
            for anchor_id in get_anchor_ids(mood_name)[:_max_anchors]:
                if _budget["calls"] >= _budget["max"]:
                    _budget_hit = True
                    break
                if anchor_id in fetched_ids:
                    continue
                try:
                    anchor_pl = sp.playlist(anchor_id)
                    time.sleep(_items_gap)
                except Exception:
                    continue
                if not anchor_pl:
                    continue
                anchor_name = anchor_pl.get("name", "")
                anchor_followers = (anchor_pl.get("followers") or {}).get("total", 0)
                anchor_tags = extract_tags(anchor_name)
                if not anchor_tags:
                    continue
                fetched_ids.add(anchor_id)
                anchor_uris = _playlist_track_uris(
                    sp, anchor_id, _mtp, _budget=_budget, _batch_gap=_batch_gap,
                )
                time.sleep(_items_gap)
                for uri in anchor_uris:
                    if uri in user_uris:
                        track_context[uri].append({
                            "playlist_id": anchor_id,
                            "playlist":    anchor_name,
                            "followers":   anchor_followers,
                            "mood":        mood_name,
                            "tags":        anchor_tags,
                        })
            if _budget_hit:
                break

            for query in queries_used:
                if _budget["calls"] >= _budget["max"]:
                    _budget_hit = True
                    break
                playlists = _search_playlists(sp, query, limit=playlists_per_seed)
                time.sleep(_search_delay)

                for pl in playlists:
                    if _budget["calls"] >= _budget["max"]:
                        _budget_hit = True
                        break
                    pid = pl.get("id")
                    if not pid or pid in fetched_ids:
                        continue

                    pl_name   = pl.get("name", "")
                    followers = (pl.get("followers") or {}).get("total", 0)
                    tags      = extract_tags(pl_name)

                    if not tags:
                        continue

                    fetched_ids.add(pid)
                    uris = _playlist_track_uris(
                        sp, pid, _mtp, _budget=_budget, _batch_gap=_batch_gap,
                    )
                    time.sleep(_items_gap)

                    for uri in uris:
                        if uri in user_uris:
                            track_context[uri].append({
                                "playlist_id": pid,
                                "playlist":    pl_name,
                                "followers":   followers,
                                "mood":        mood_name,
                                "tags":        tags,
                            })
                if _budget_hit:
                    break
            if _budget_hit:
                break

        if _budget_hit:
            print(
                f"\r  Search stopped early  playlist_items budget ({_max_calls}) · "
                f"{len(fetched_ids)} playlists          "
            )
        else:
            print(f"\r  Search complete       {len(fetched_ids)} playlists · "
                  f"{len(track_context)} tracks matched          ")

    # ── Build weighted tag scores (phrase boost + semantic expansion) ─────────
    track_tags: dict[str, dict[str, float]] = {}
    tag_index: dict[str, list[str]] = collections.defaultdict(list)

    for uri, contexts in track_context.items():
        raw_weights: dict[str, float] = collections.defaultdict(float)
        for ctx in contexts:
            followers = ctx.get("followers", 1000)
            if ctx.get("mood") is None:  # owned playlists have mood=None
                authority = 3.5  # owned playlists: strong user signal, bypass log formula
            else:
                authority = math.log10(max(followers, 1) + 1)
            for tag in ctx["tags"]:
                # Phrase-boosted: "late_night_drive" (3×) > "drive" (1×)
                # Authority-weighted: larger playlists contribute more signal
                raw_weights[tag] += _tag_weight(tag) * authority

        if raw_weights:
            # Semantic expansion: "late_night_drive" implies "introspective",
            # "dark", "drive", "night" at 0.5× weight — adds depth without ML
            expanded = _apply_semantic_expansion(dict(raw_weights))
            max_w = max(expanded.values())
            _built = {t: round(w / max_w, 4) for t, w in expanded.items()}
            # Merge in canonical cluster names so scoring vocabulary aligns
            _clusters = _collapse_tags(_built)
            track_tags[uri] = {**_built, **_clusters} if _clusters else _built
        else:
            track_tags[uri] = {}
        for tag in track_tags[uri]:
            if uri not in tag_index[tag]:
                tag_index[tag].append(uri)

    # ── Public playlist finder: top playlists per mood by user overlap ────────
    mood_fit_playlists: dict[str, list[dict]] = collections.defaultdict(list)
    pl_overlap_count: dict[str, dict] = {}  # key → {mood, name, followers, count}

    for uri, contexts in track_context.items():
        for ctx in contexts:
            pid = ctx.get("playlist_id", "")
            if not pid:
                continue
            mood = ctx["mood"]
            key  = f"{pid}::{mood}"
            if key not in pl_overlap_count:
                pl_overlap_count[key] = {
                    "id":        pid,
                    "name":      ctx["playlist"],
                    "followers": ctx["followers"],
                    "mood":      mood,
                    "count":     0,
                }
            pl_overlap_count[key]["count"] += 1

    for entry in pl_overlap_count.values():
        mood_fit_playlists[entry["mood"]].append(entry)

    for mood_name in mood_fit_playlists:
        mood_fit_playlists[mood_name].sort(key=lambda x: -x["count"])
        mood_fit_playlists[mood_name] = mood_fit_playlists[mood_name][:5]

    total_tagged = sum(1 for t in track_tags.values() if t)
    print(f"  Mining complete       {len(fetched_ids)} playlists · "
          f"{total_tagged}/{len(user_uris)} tracks tagged")

    _own_items_blocked = own.get("playlist_items_blocked", False)
    result = {
        "track_tags":              track_tags,
        "track_context":           {k: v for k, v in track_context.items()},
        "tag_index":               dict(tag_index),
        "mood_fit_playlists":      dict(mood_fit_playlists),
        "blocked":                 _probe_blocked,
        "playlist_items_blocked":  _probe_blocked or _own_items_blocked,
    }
    _save_cache(result)
    return result


def mood_observed_tag_weights(track_context: dict, mood_name: str) -> dict[str, float]:
    """
    Aggregate tag weights from mining contexts tied to a specific mood
    (public/anchor playlists labeled with that mood). Used to blend real
    playlist vocabulary into expected tags via scorer.combine_expected_tags.

    The result is run through collapse_tags so it uses the same canonical
    cluster vocabulary as track_tags profiles — preventing "midnight"/"driving"
    style vocabulary mismatches when the scorer compares expected tags against
    track tag_clusters.
    """
    raw_weights: dict[str, float] = collections.defaultdict(float)
    for uri, ctxs in track_context.items():
        for ctx in ctxs:
            if ctx.get("mood") != mood_name:
                continue
            followers = ctx.get("followers", 1000)
            authority = math.log10(max(followers, 1) + 1)
            for tag in ctx.get("tags", []):
                raw_weights[tag] += _tag_weight(tag) * authority

    raw = dict(raw_weights)
    # Normalize to [0,1] then collapse to canonical cluster names
    if raw:
        max_w = max(raw.values())
        if max_w > 0:
            raw = {t: round(w / max_w, 4) for t, w in raw.items()}
    collapsed = _collapse_tags(raw)
    # Merge: collapsed cluster names take precedence; raw raw tags fill rest
    return {**raw, **collapsed} if collapsed else raw
