"""
scorer.py — Multi-signal scoring engine.

Formula:
  score = w_audio * audio_similarity
        + w_tags  * tag_similarity
        + w_genre * genre_match
        + w_pref  * user_preference_boost

Weights default to: 0.45, 0.35, 0.20
User preference boost multiplies the final score when tuned.

This produces a ranked list of tracks for any target mood.
"""

import collections
import json
import math
import os

import config as _cfg

from core.mood_graph import (
    cosine_similarity,
    gaussian_similarity,
    mood_audio_target,
    mood_audio_constraints,
    mood_expected_tags,
    mood_preferred_genres,
    mood_forbidden_tags,
    mood_forbidden_genres,
    mood_semantic_core,
    mood_semantic_similarity,
    mood_genre_neutral,
    mood_lyric_focus,
    mood_lyrical_expected_tags,
)


# Scoring weights from config (.env). W_AUDIO removed — deprecated endpoint.
W_METADATA_AUDIO   = _cfg.W_METADATA_AUDIO
W_TAGS             = _cfg.W_TAGS
W_SEMANTIC         = _cfg.W_SEMANTIC
W_GENRE            = _cfg.W_GENRE


# Prefixes that identify unambiguously per-track signals (not artist-level fallback).
_PER_TRACK_PREFIXES: tuple[str, ...] = (
    "lyr_",         # per-track lyric signals (NRC + VADER + keyword)
    "bpm_",         # per-track tempo bucket
    "meta_",        # per-track metadata signals (duration, position, feat., title keywords)
    "mood_",        # Last.fm tag-chart matches (per-track ground truth)
    "anchor_",      # curated anchor track matches (per-track ground truth)
    "graph_mood_",  # graph-propagated anchor labels (agreement layer)
)


def _signal_confidence(tags: dict[str, float]) -> float:
    """
    Estimate the fraction of per-track signal available for a track.

    Returns [0.0, 1.0] — higher means more specific per-track data exists,
    which lets tag_score() proportionally downweight artist-level fallback tags.

    Confidence increments (capped at 1.0):
      lyr_* present           → +0.35  (lyric analysis: NRC + VADER + keywords)
      bpm_* or meta_* present → +0.20  (tempo bucket or structural metadata)
      mood_*, anchor_*,
      or graph_mood_*         → +0.45  (Last.fm chart / anchor / graph agreement)
      dz_bpm present          → +0.10  (real Deezer BPM available)
    """
    conf = 0.0
    if any(k.startswith("lyr_") for k in tags):
        conf += 0.35
    if any(k.startswith("bpm_") or k.startswith("meta_") for k in tags):
        conf += 0.20
    if any(k.startswith("mood_") or k.startswith("anchor_") or k.startswith("graph_mood_") for k in tags):
        conf += 0.45
    if "dz_bpm" in tags:
        conf += 0.10
    return min(conf, 1.0)


def get_active_tags(profile: dict) -> dict[str, float]:
    """
    Return the unified tag signal for scoring.

    Merges raw mined tags with canonical cluster names so both vocabularies
    are active simultaneously:
      - Raw tags  → rich mined vocabulary ("late_night_drive", "gym", "phonk")
      - Clusters  → canonical names ("night", "sad") for exact expected-tag matching

    Precedence: clusters override raw tags for the same canonical key (the
    collapsed weight is already the max of all member tags, so it's at least
    as strong as any individual raw tag in the cluster).
    """
    raw      = profile.get("tags", {})
    clusters = profile.get("tag_clusters", {})
    if not clusters:
        return raw
    return {**raw, **clusters}


_USER_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "outputs",
    ".user_model.json",
)
_user_model_cache: dict | None = None


def _load_user_model() -> dict:
    global _user_model_cache
    if _user_model_cache is not None:
        return _user_model_cache
    try:
        if os.path.exists(_USER_MODEL_PATH):
            with open(_USER_MODEL_PATH, encoding="utf-8") as f:
                _user_model_cache = json.load(f)
        else:
            _user_model_cache = {}
    except (OSError, json.JSONDecodeError):
        _user_model_cache = {}
    return _user_model_cache


def resolved_score_weights(
    base: tuple[float, float, float, float] | None = None,
) -> tuple[float, float, float, float]:
    """
    Merge config defaults with optional outputs/.user_model.json score_weights
    (from ml.train_weights). Normalises to sum 1.0. Keys: w_audio, w_tags,
    w_semantic, w_genre.
    """
    b = base if base is not None else (W_METADATA_AUDIO, W_TAGS, W_SEMANTIC, W_GENRE)
    model = _load_user_model()
    sw = model.get("score_weights") if isinstance(model, dict) else None
    if not sw or not isinstance(sw, dict):
        return b
    wa = float(sw.get("w_audio", b[0]))
    wt = float(sw.get("w_tags", b[1]))
    ws = float(sw.get("w_semantic", b[2]))
    wg = float(sw.get("w_genre", b[3]))
    s = wa + wt + ws + wg
    if s <= 0:
        return b
    return (wa / s, wt / s, ws / s, wg / s)


def user_model_score_multiplier(profile: dict) -> float:
    """
    Bounded lift from outputs/.user_model.json tag_biases (from ml/train_weights.py).
    """
    model = _load_user_model()
    biases = model.get("tag_biases") if isinstance(model, dict) else None
    if not biases:
        return 1.0
    tags = get_active_tags(profile)
    adj = 0.0
    for tag, w in tags.items():
        b = biases.get(tag)
        if b is not None:
            adj += float(b) * min(float(w), 1.0)
    return max(0.88, min(1.12, 1.0 + adj))


# ── Semantic synonym clusters ─────────────────────────────────────────────────
# Each list is a cluster of interchangeable/related terms.
# A mined tag that falls in the same cluster as an expected tag scores at 0.45×.
# This lets "crying" match "sad", "2am" match "night", "heartbreak" match "broken", etc.

_SYNONYM_CLUSTERS: list[list[str]] = [
    # ── Sadness / grief
    ["sad", "sadness", "crying", "cry", "tears", "weep", "grief", "grieve",
     "hollow", "heartbreak", "heartbroken", "broken", "hurt", "pain", "ache",
     "sorrow", "sorrowful", "misery", "miserable", "blue", "depressed", "depression",
     "numb", "empty", "hopeless", "desolate", "forlorn", "bereft", "woe"],

    # ── Loneliness / isolation
    ["lonely", "loneliness", "alone", "solitude", "isolated", "isolation",
     "abandoned", "forgotten", "miss", "missing", "lost", "invisible"],

    # ── Breakup / love lost
    ["breakup", "break_up", "heartbreak", "heartbroken", "ex", "gone",
     "over", "miss", "missing", "goodbye", "ended", "apart", "distance"],

    # ── Night / late hours
    ["night", "nights", "nighttime", "late_night", "midnight", "2am", "3am", "4am",
     "1am", "after_midnight", "nocturnal", "insomnia", "sleepless", "dark_hours",
     "wee_hours", "late", "after_dark", "night_owl", "witching_hour"],

    # ── Rain / weather melancholy
    ["rain", "rainy", "raining", "rainfall", "stormy", "storm", "grey", "gray",
     "overcast", "cloudy", "drizzle", "wet", "damp", "fog", "foggy", "mist", "misty"],

    # ── Driving / journey
    ["drive", "driving", "driver", "road", "highway", "cruise", "cruising",
     "windows_down", "open_road", "ride", "riding", "car", "headlights", "freeway",
     "streets", "backroads", "route", "journey", "trip", "travel"],

    # ── City / urban
    ["city", "urban", "downtown", "streets", "neon", "lights", "skyline",
     "downtown", "metropolitan", "metro", "concrete", "pavement", "alley",
     "underground", "subway", "night_city", "rooftop", "apartment"],

    # ── Energy / hype
    ["hype", "hyped", "energy", "energetic", "lit", "fire", "flames", "turnt",
     "banger", "beast_mode", "power", "pump", "pumped", "charge", "charged",
     "electric", "high_energy", "amped", "amped_up", "explosive", "intense"],

    # ── Workout / gym
    ["gym", "workout", "training", "lift", "lifting", "weights", "gains",
     "fitness", "run", "running", "cardio", "sprint", "beast", "grind",
     "hustle", "hard_work", "discipline", "sweat"],

    # ── Party / celebration
    ["party", "parties", "celebration", "celebrate", "turn_up", "club",
     "dance", "dancing", "dancefloor", "floor", "rave", "festival",
     "anthem", "crowd", "vibe", "vibes", "good_times", "pregame", "shots"],

    # ── Happy / joy
    ["happy", "happiness", "joy", "joyful", "bliss", "blissful", "euphoria",
     "euphoric", "elated", "elation", "cheerful", "upbeat", "positive",
     "sunshine", "bright", "light", "smile", "smiling", "giddy", "gleeful"],

    # ── Chill / relaxed
    ["chill", "chilled", "chilling", "relax", "relaxed", "relaxing", "calm",
     "calming", "mellow", "laid_back", "easy", "slow", "smooth", "soothing",
     "peaceful", "serene", "tranquil", "gentle", "soft", "cozy", "comfy"],

    # ── Focus / study
    ["focus", "focused", "study", "studying", "work", "working", "concentrate",
     "concentration", "productive", "productivity", "flow", "deep_work",
     "reading", "homework", "grind", "hustle", "brain", "think", "thinking"],

    # ── Sleep / ambient
    ["sleep", "sleeping", "sleepy", "tired", "drowsy", "rest", "resting",
     "bedtime", "dream", "dreaming", "drift", "drifting", "lullaby",
     "ambient", "atmospheric", "ethereal", "weightless", "float", "floating"],

    # ── Nostalgia / memories
    ["nostalgia", "nostalgic", "memories", "memory", "remember", "remembering",
     "throwback", "old", "past", "vintage", "retro", "classic", "childhood",
     "youth", "younger", "simpler", "back_then", "used_to", "miss", "bittersweet"],

    # ── Summer / warmth
    ["summer", "summertime", "sunshine", "sunny", "sun", "warm", "warmth",
     "heat", "beach", "ocean", "waves", "pool", "vacation", "holiday",
     "hot", "golden", "tan", "glow", "bbq", "outdoor", "outside"],

    # ── Romantic / love
    ["love", "romance", "romantic", "lover", "lovers", "crush", "crush_on",
     "date", "dating", "together", "together_forever", "us", "you_and_me",
     "darling", "sweetheart", "adore", "adoration", "affection", "tender",
     "intimate", "intimacy", "heart", "valentine", "wedding"],

    # ── Sexy / sensual
    ["sexy", "sensual", "seductive", "flirt", "flirty", "desire", "passion",
     "passionate", "hot", "sultry", "lust", "lustful", "tempt", "temptation",
     "bedroom", "late_night", "slow_jam", "rnb", "groove", "smooth"],

    # ── Angry / aggressive
    ["angry", "anger", "rage", "furious", "fury", "mad", "pissed", "hate",
     "hatred", "aggressive", "aggression", "brutal", "raw", "intense",
     "explosive", "hard", "heavy", "dark", "frustrated", "frustration",
     "bitter", "bitterness", "spite", "scorned", "betrayal", "seething",
     "not_over_it", "burning_bridges", "revenge"],

    # ── Melancholic / moody
    ["melancholy", "melancholic", "moody", "mood", "pensive", "pensieve",
     "contemplative", "reflective", "introspective", "bittersweet", "wistful",
     "wistfulness", "yearning", "longing", "aching", "weighted", "weighed_down"],

    # ── Morning / dawn
    ["morning", "sunrise", "dawn", "wake", "waking", "early", "fresh_start",
     "new_day", "coffee", "gentle_morning", "soft_morning", "rise", "arising"],

    # ── Sunset / evening
    ["sunset", "dusk", "evening", "golden_hour", "twilight", "afterglow",
     "end_of_day", "wind_down", "wrap_up", "close"],

    # ── Confident / powerful
    ["confident", "confidence", "power", "powerful", "boss", "boss_up",
     "winning", "winner", "unstoppable", "invincible", "strong", "strength",
     "fearless", "bold", "badass", "slay", "slaying", "queen", "king"],

    # ── Spiritual / transcendent
    ["spiritual", "spirit", "soul", "soulful", "divine", "sacred", "holy",
     "transcendent", "ascend", "heaven", "ethereal", "cosmic", "universe",
     "meditate", "meditation", "prayer", "worship", "faith",
     "gospel", "choir", "church", "praise", "blessed", "anointed",
     "congregation", "revival", "sanctified"],

    # ── Dark / sinister
    ["dark", "darkness", "sinister", "eerie", "creepy", "gothic", "goth",
     "shadow", "shadows", "void", "abyss", "black", "noir", "ominous",
     "haunted", "haunting", "macabre", "twisted", "cold",
     "darkwave", "post_punk", "coldwave", "deathrock", "morose"],

    # ── Indie / alternative feel
    ["indie", "alternative", "alt", "underground", "bedroom_pop", "lo_fi",
     "lofi", "lo-fi", "raw", "acoustic", "stripped", "authentic",
     "honest", "real", "vulnerable", "open", "personal"],

    # ── Hip-hop / rap energy
    ["rap", "rapper", "bars", "spitting", "flow", "freestyle", "trap",
     "drill", "boom_bap", "hip_hop", "hiphop", "hip-hop", "street",
     "hustle", "grind", "real", "authentic", "raw"],

    # ── Electronic / synth
    ["electronic", "synth", "synthesizer", "techno", "edm", "house",
     "trance", "beats", "bpm", "drop", "bass", "bassline", "808",
     "rave", "club", "dj", "mix", "remix", "produce", "produced",
     "synthwave", "retrowave", "outrun", "cyberpunk", "vaporwave",
     "neon", "retro_future", "80s_synth"],

    # ── Psychedelic / mind-expanding
    ["psychedelic", "trippy", "mind_expanding", "acid", "swirling",
     "dissolving", "kosmische", "phased", "wormhole", "third_eye",
     "lysergic", "space_rock", "psych", "mind_bending",
     "kaleidoscope", "sonic_journey", "head_music"],

    # ── Jazz / blues atmosphere
    ["jazz", "blues", "soul_jazz", "bebop", "swing", "smoky",
     "lounge", "piano_bar", "upright_bass", "brushed_drums",
     "muted_trumpet", "late_night_jazz", "cocktail", "sophisticated"],

    # ── Drill / cold street
    ["drill", "uk_drill", "ny_drill", "cold_verse", "dark_melody",
     "rolling_hats", "street_cold", "menacing", "predatory",
     "concrete_dark", "block_life", "road_life", "hostile"],

    # ── Gospel / uplift
    ["gospel", "worship", "praise", "choir", "church", "blessed",
     "holy", "spiritual_uplift", "transcendent_joy", "anointed",
     "soul_revival", "spirit_filled", "congregation"],

    # ── Neo-soul / organic R&B
    ["neo_soul", "organic_groove", "conscious_r&b", "soulful_delivery",
     "vintage_soul", "groove_pocket", "earthy_production",
     "head_nod_soul", "warm_bass", "live_feel", "soulful_vocal"],

    # ── K-pop / idol pop
    ["k_pop", "kpop", "idol", "comeback", "k_pop_group",
     "j_pop", "jpop", "korean_pop", "girl_group", "boy_band",
     "fandom", "choreography", "stage_performance", "catchy_hook"],

    # ── Bedroom / personal indie
    ["bedroom_pop", "lo_fi_indie", "cassette_warmth", "indie_soft",
     "home_recording", "pillow_soft", "hazy_indie", "cozy_indie",
     "indie_crush", "bedroom_daydream", "personal_indie"],

    # ── Country / americana
    ["country", "americana", "twang", "southern_storytelling",
     "pickup_truck", "porch", "rural", "heartland", "outlaw_country",
     "country_soul", "country_heartbreak", "gravel_road", "boots"],
]

# Build a flat lookup: term → cluster_index
_TERM_TO_CLUSTER: dict[str, int] = {}
for _i, _cluster in enumerate(_SYNONYM_CLUSTERS):
    for _term in _cluster:
        _TERM_TO_CLUSTER[_term] = _i


def _synonym_match(expected_tag: str, mined_tag: str) -> bool:
    """Return True if expected_tag and mined_tag share a synonym cluster."""
    ci_expected = _TERM_TO_CLUSTER.get(expected_tag)
    ci_mined    = _TERM_TO_CLUSTER.get(mined_tag)
    if ci_expected is None or ci_mined is None:
        return False
    return ci_expected == ci_mined


# ── Neutral-vector detection ──────────────────────────────────────────────────

_NEUTRAL = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]


def _is_neutral_vector(v: list[float]) -> bool:
    """
    Return True if the audio vector is the fallback [0.5]*6 sentinel.

    profile.py emits this when no Spotify audio features are available.
    Treating it as a valid signal causes every neutral track to appear
    "similar" to all moods — a silent poison.  We return 0.0 audio score
    instead so these tracks compete only on tags + genre.
    """
    return len(v) == 6 and all(abs(x - 0.5) < 1e-9 for x in v)


def effective_score_weights(
    profile: dict,
    weights: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """
    When audio_vector_source is metadata_proxy, allocate W_METADATA_AUDIO to the
    audio term and rescale tag/semantic/genre so the four sum to 1.0.
    """
    wa, wt, ws, wg = weights
    if (
        profile.get("audio_vector_source") == "metadata_proxy"
        and not _is_neutral_vector(profile.get("audio_vector") or _NEUTRAL)
    ):
        wma = float(getattr(_cfg, "W_METADATA_AUDIO", 0.1))
        rest = 1.0 - wma
        s = wt + ws + wg
        if s > 0 and rest >= 0:
            k = rest / s
            return (wma, wt * k, ws * k, wg * k)
    return (wa, wt, ws, wg)


def library_real_audio_fraction(
    profiles: dict[str, dict],
    sample_limit: int = 500,
) -> float:
    """Share of profiles (up to sample_limit) that have real Spotify audio features."""
    n = 0
    real = 0
    for p in profiles.values():
        n += 1
        if n > sample_limit:
            break
        v = p.get("audio_vector") or _NEUTRAL
        if not _is_neutral_vector(v):
            real += 1
    return real / max(n, 1)


def cohesion_signal_weights(profiles: dict[str, dict]) -> tuple[float, float, float]:
    """
    Return (audio_weight, tag_weight, semantic_weight) for cohesion_filter.

    Real Spotify audio features → full 0.40 audio weight.
    Metadata proxy vectors     → 0.20 audio weight (heuristic, not ground truth).
    Neutral / no vectors       → 0.0 audio weight, pure tag+semantic.
    """
    real_frac = library_real_audio_fraction(profiles)
    if real_frac >= 0.05:
        return (0.40, 0.30, 0.30)
    # Check if proxy vectors are present (non-neutral)
    proxy_count = sum(
        1 for p in list(profiles.values())[:500]
        if p.get("audio_vector_source") == "metadata_proxy"
        and not _is_neutral_vector(p.get("audio_vector") or _NEUTRAL)
    )
    sample = min(500, len(profiles))
    if proxy_count / max(sample, 1) >= 0.20:
        # Proxy vectors exist but are heuristic — use small audio weight
        return (0.15, 0.47, 0.38)
    return (0.0, 0.50, 0.50)


# ── Hard audio constraint filter ──────────────────────────────────────────────

def passes_hard_filters(profile: dict, mood_name: str) -> bool:
    """
    Return False if the track violates any hard audio constraint for the mood.

    Constraints live in packs.json under ``audio_constraints`` and express
    absolute min/max bounds on energy and valence.  They act as a fast-reject
    gate run BEFORE scoring so garbage tracks never reach the ranker.

    If audio features are unavailable (empty ``_features``), the track passes
    automatically — we cannot reject what we cannot measure.

    PROXY MODE (metadata_proxy source):
    When real Spotify audio features are unavailable (e.g. Dev Mode), all tracks
    receive heuristic proxy estimates from genre/tag signals.  We apply constraints
    with a ±0.15 tolerance buffer so only clear violators are rejected.

    The buffer handles genuine proxy inaccuracy: a track tagged "metal" gets
    proxy energy≈0.85 but could be a mellow ballad, so we only reject at > 0.95
    (0.80 + 0.15).  The 841 tracks with neutral proxy energy=0.50 (no genre signal)
    pass all constraints because 0.50 is well inside any buffered range.
    """
    _PROXY_TOLERANCE = 0.15   # margin applied to each constraint bound in proxy mode

    features = profile.get("_features") or {}
    if not features:
        return True  # no data → cannot filter

    constraints = mood_audio_constraints(mood_name)
    if not constraints:
        return True

    energy  = features.get("energy",  0.5)
    valence = features.get("valence", 0.5)
    _is_proxy = features.get("_source") == "metadata_proxy"

    if _is_proxy:
        # Soft-apply constraints with tolerance buffer — only reject clear violators.
        tol = _PROXY_TOLERANCE
        if "energy_min"  in constraints and energy  < constraints["energy_min"]  - tol:
            return False
        if "energy_max"  in constraints and energy  > constraints["energy_max"]  + tol:
            return False
        if "valence_min" in constraints and valence < constraints["valence_min"] - tol:
            return False
        if "valence_max" in constraints and valence > constraints["valence_max"] + tol:
            return False
        return True

    if "energy_min"  in constraints and energy  < constraints["energy_min"]:
        return False
    if "energy_max"  in constraints and energy  > constraints["energy_max"]:
        return False
    if "valence_min" in constraints and valence < constraints["valence_min"]:
        return False
    if "valence_max" in constraints and valence > constraints["valence_max"]:
        return False

    return True


# ── Negative signal filter (weighted penalties) ───────────────────────────────

def negative_filter_penalty(
    profile: dict,
    mood_name: str,
    penalty_cap: float = 0.75,
) -> float:
    """
    Return a weighted score penalty [0.0, penalty_cap] for forbidden signals.

    Unlike binary rejection, this lets borderline tracks survive — just
    scored lower.  A track with one mildly conflicting tag still makes the
    playlist; a track soaked in anti-vibe signals gets capped at near-zero.

    Only hard audio constraints (energy / valence bounds) remain binary gates.

    Penalty schedule (proportional to actual tag weight):
      tag_weight * 0.6  per matching forbidden tag
        A tag with weight 0.9 → +0.54 penalty
        A tag with weight 0.2 → +0.12 penalty (minor presence = minor penalty)
      +0.50 flat for any forbidden genre match

    Proportional formula stops low-weight accidental tag matches from killing
    otherwise-good tracks.  High-weight forbidden tags still hurt significantly.

    penalty_cap values:
      1.0 (default) — no floor; heavily conflicting tracks reach zero
      0.50           — MVP / thin playlist mode (softer, more tracks survive)

    Args:
        profile:     Track profile dict from profile.build().
        mood_name:   Target mood name (must match a packs.json key).
        penalty_cap: Maximum total penalty to apply.

    Returns:
        Float in [0.0, penalty_cap].  Caller applies: score *= (1 - penalty).
    """
    forbidden_t = mood_forbidden_tags(mood_name)
    forbidden_g = mood_forbidden_genres(mood_name)
    track_tags  = get_active_tags(profile)

    penalty = 0.0

    if forbidden_t and track_tags:
        from core.profile import _TAG_TO_CLUSTER  # noqa: PLC0415
        # Resolve each forbidden tag to its canonical cluster name so the check
        # works even when packs.json uses raw tag names ("worship", "gym", etc.)
        # instead of cluster names ("spiritual", "hype").
        resolved_ft = set()
        for ft in forbidden_t:
            resolved_ft.add(ft)
            cluster = _TAG_TO_CLUSTER.get(ft)
            if cluster:
                resolved_ft.add(cluster)
        for tag, weight in track_tags.items():
            for ft in resolved_ft:
                if tag == ft or tag.startswith(ft) or ft.startswith(tag):
                    penalty += weight * 0.6  # proportional to how strongly the track is tagged
                    break

    if forbidden_g:
        macro_genres = set(profile.get("macro_genres", []))
        for fg in forbidden_g:
            if fg in macro_genres:
                penalty += 0.50  # flat genre penalty
                break

    return min(penalty, penalty_cap)


def passes_negative_filters(profile: dict, mood_name: str) -> bool:
    """
    Legacy binary compatibility shim.

    Returns False only for extreme conflicts (penalty ≥ 0.90 — track carries
    very high-weight forbidden tags AND a forbidden genre simultaneously).
    Prefer negative_filter_penalty() for all new scoring code.
    """
    return negative_filter_penalty(profile, mood_name) < 0.90


# ── Taste adaptation boost ────────────────────────────────────────────────────

def taste_adaptation_boost(
    profile: dict,
    user_tag_prefs: dict[str, float] | None,
) -> float:
    """
    Personalise scores using the user's observed tag preferences.

    Computes the average preference weight for the track's tags and maps it
    to a multiplier in [0.90, 1.10].  Tracks whose tags align with the user's
    listening history get a small lift; tracks with no alignment get a small
    reduction.

    Args:
        profile:        Track profile dict.
        user_tag_prefs: Output of profile.user_tag_preferences() —
                        {tag: avg_weight_across_library}.
                        Pass None / {} to disable.

    Returns:
        Float multiplier in [0.90, 1.10].
    """
    active_tags = get_active_tags(profile)
    if not user_tag_prefs or not active_tags:
        return 1.0
    # Exclude numeric pseudo-tags (dz_bpm, vader_valence) — their raw float values
    # (e.g. 193.2 BPM) are not in [0, 1] and inflate avg catastrophically.
    _NUMERIC = frozenset({"dz_bpm", "vader_valence"})
    total = sum(user_tag_prefs.get(tag, 0.0) for tag in active_tags if tag not in _NUMERIC)
    denom = sum(1 for tag in active_tags if tag not in _NUMERIC)
    if denom == 0:
        return 1.0
    avg   = total / denom
    # Map avg in [0, 1] → multiplier in [0.90, 1.10].
    # Clamp strictly — raw numeric tag values must never escape into the multiplier.
    return round(max(0.90, min(1.10, 0.90 + avg * 0.20)), 6)


# ── Positive match boost ──────────────────────────────────────────────────────

def positive_boost(
    profile: dict,
    mood_name: str,
    expected_tags: list[str] | None = None,
) -> float:
    """
    Reward tracks with strong overlap on the mood's EXPECTED tags.

    The base score rewards everything proportionally, but does not give extra
    credit for tracks that hit expected tags with high weight (perfect fits).
    This multiplier fixes that gap:

      overlap   = sum of profile tag weights for each expected tag that matches
      strength  = overlap / len(expected_tags)     (normalised [0, 1])
      boost     = 1.0 + 0.15 * min(strength, 1.0)  (up to 1.15×)

    A track that hits 6 of 6 expected tags all at weight 1.0 gets 1.15×.
    A track that misses all expected tags gets exactly 1.0× (no change).

    This is the complement of negative_filter_penalty:
      negative_filter_penalty → reduces wrong vibes
      positive_boost          → rewards right vibes

    Args:
        expected_tags: If set (e.g. merged static + mining tags), use instead of
            mood_expected_tags(mood_name).

    Returns:
      Float multiplier in [1.0, 1.15].
    """
    tags     = get_active_tags(profile)
    expected = expected_tags if expected_tags is not None else mood_expected_tags(mood_name)
    if not tags or not expected:
        return 1.0
    overlap  = sum(tags.get(t, 0.0) for t in expected)
    strength = overlap / len(expected)
    return 1.0 + 0.15 * min(strength, 1.0)


# ── Conflict detection ────────────────────────────────────────────────────────

# Pairs of tags that actively contradict each other when BOTH appear in a track.
# Only intra-track conflicts count — a track with both "calm" and "aggressive"
# tags is genuinely contradictory and should be penalised.
#
# Each base tag maps to the set of tags that conflict with it.
# Penalty per conflicting pair: 0.40.  Total capped at 1.0.
_CONFLICT_MAP: dict[str, set[str]] = {
    "calm":         {"aggressive", "rage", "drill", "hype", "metal", "angry", "chaotic"},
    "aggressive":   {"calm", "ambient", "sleep", "peaceful", "soft", "gentle"},
    "peaceful":     {"aggressive", "rage", "hype", "chaotic", "angry", "metal"},
    "romantic":     {"rage", "drill", "metal", "aggressive", "angry"},
    "focus":        {"party", "club", "hype", "rave", "chaotic"},
    "sleep":        {"hype", "party", "aggressive", "gym", "energy", "chaotic"},
    "worship":      {"rage", "aggressive", "angry", "metal", "drill"},
    "happy":        {"hollow", "numb", "desolate", "despair"},
    "sad":          {"hype", "euphoric", "party", "turnt"},
    "ambient":      {"aggressive", "hype", "chaotic", "rage", "gym"},
}


def conflict_penalty(profile: dict) -> float:
    """
    Penalise tracks whose own tags actively contradict each other.

    A track tagged both "calm" and "aggressive" is genuinely incoherent —
    no mood should want it.  Each detected contradiction adds 0.40 penalty,
    capped at 1.0 (full suppression for maximally conflicted tracks).

    This is mood-independent: if a track contradicts itself, it's a bad fit
    everywhere.  It fires AFTER negative_filter_penalty so the combined effect
    can suppress heavily conflicted tracks completely.

    Returns:
        Float in [0.0, 1.0].  Caller applies: score *= (1 - conflict_penalty).
    """
    tags = set(get_active_tags(profile).keys())
    if len(tags) < 2:
        return 0.0

    penalty = 0.0
    seen_pairs: set[frozenset] = set()

    for base, opposites in _CONFLICT_MAP.items():
        if base in tags:
            for opp in opposites:
                if opp in tags:
                    pair = frozenset({base, opp})
                    if pair not in seen_pairs:
                        penalty += 0.40
                        seen_pairs.add(pair)

    return min(penalty, 1.0)


# ── Adaptive strictness ───────────────────────────────────────────────────────

def adaptive_threshold(n_tracks: int) -> float:
    """
    Return the cohesion threshold to apply given the playlist's current size.

    Adaptive logic:
      Few tracks (< 20) → HIGH threshold (0.85)
        Every slot matters — only keep tracks very close to the centroid.
        Tighter playlist beats a longer, unfocused one.
      Moderate (< 40)   → MEDIUM threshold (0.70)
        Balance cohesion and variety.
      Large (≥ 40)      → LOWER threshold (0.60)
        With many qualified tracks, allow slightly more variety while still
        filtering clear outliers.

    Args:
        n_tracks: Number of scored tracks BEFORE cohesion filtering.

    Returns:
        Float cohesion threshold for cohesion_filter().
    """
    if n_tracks < 20:
        return 0.85
    elif n_tracks < 40:
        return 0.70
    return 0.60


# ── User model — full signal loop ─────────────────────────────────────────────

def user_model_penalty(
    profile: dict,
    disliked_tags: set[str] | None = None,
    avoided_genres: set[str] | None = None,
    recent_uris: list[str] | None = None,
    recency_penalty: float = 0.10,
) -> float:
    """
    Apply user-model–based score penalties on top of mood-specific scoring.

    Three sub-signals — all optional, each independent:

    Disliked tags   (from explicit user feedback or inferred from skips)
      The user has indicated these tags consistently disappoint.
      Each matching tag adds 0.20 penalty.  Max cap: 0.60.
      Example: user always skips rap tracks → "rap", "bars", "trap" in disliked.

    Avoided genres  (from explicit feedback or genre-skipping patterns)
      The user consistently dislikes tracks from these macro genres.
      Any match adds 0.30 penalty.  Max cap: 0.50.

    Recency bias    (recently played tracks get a small penalty)
      Prevents the same tracks from dominating every playlist run.
      A fixed recency_penalty (default 0.10) is applied if the track URI
      appears in the recent_uris list.

    Total penalty is summed and capped at 0.80 so tracks are degraded,
    not erased — consistent with the weighted negative filter philosophy.

    Args:
        profile:         Track profile dict.
        disliked_tags:   Set of tag strings the user dislikes.
        avoided_genres:  Set of macro-genre strings to avoid.
        recent_uris:     List of recently-played track URIs.
        recency_penalty: Penalty applied if the track is in recent_uris.

    Returns:
        Float penalty in [0.0, 0.80].  Apply as: score *= (1 - penalty).
    """
    penalty = 0.0

    # Disliked tags
    if disliked_tags:
        track_tags = set(get_active_tags(profile).keys())
        for dt in disliked_tags:
            if dt in track_tags:
                penalty += 0.20

    # Avoided genres
    if avoided_genres:
        macro_genres = set(profile.get("macro_genres", []))
        if macro_genres & avoided_genres:
            penalty += 0.30

    # Recency bias
    if recent_uris and profile.get("uri") in recent_uris:
        penalty += recency_penalty

    return min(penalty, 0.80)


def build_user_model(
    profiles: dict[str, dict],
    skip_uris: set[str] | None = None,
    disliked_tag_threshold: float = 0.30,
) -> dict:
    """
    Derive a lightweight user model from library profiles + explicit feedback.

    The user model captures three things:
      tag_prefs      — average tag weight across library (for taste_adaptation_boost)
      disliked_tags  — tags that appear ONLY in explicitly skipped/disliked tracks
                       and never in liked ones (threshold-based)
      avoided_genres — genres that appear exclusively in skipped tracks

    This is the INFERRED model.  Explicit feedback (thumbs-down, skips) should
    be passed in as skip_uris and will override inferred preferences.

    Args:
        profiles:               {uri: profile} from profile.build_all().
        skip_uris:              URIs explicitly marked as disliked/skipped.
                                Pass None / empty to use only inferred model.
        disliked_tag_threshold: Min fraction of skip tracks a tag must appear in
                                (vs liked tracks) to be flagged as disliked.

    Returns:
        {
          "tag_prefs":      {tag: avg_weight},    — for taste_adaptation_boost
          "disliked_tags":  set[str],              — for user_model_penalty
          "avoided_genres": set[str],              — for user_model_penalty
          "recent_uris":    list[str],             — for user_model_penalty
        }
    """
    # Tag preferences across the full library
    tag_totals: dict[str, float] = {}
    tag_counts: dict[str, int]   = {}
    for p in profiles.values():
        for tag, w in get_active_tags(p).items():
            tag_totals[tag] = tag_totals.get(tag, 0.0) + w
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    tag_prefs = {t: tag_totals[t] / tag_counts[t] for t in tag_totals}

    # Skip-based disliked tags / avoided genres
    disliked_tags:  set[str] = set()
    avoided_genres: set[str] = set()

    if skip_uris:
        skip_set   = set(skip_uris)
        liked_set  = set(profiles.keys()) - skip_set

        skip_tag_freq:  dict[str, int] = collections.Counter()
        liked_tag_freq: dict[str, int] = collections.Counter()
        skip_genre_freq:  dict[str, int] = collections.Counter()
        liked_genre_freq: dict[str, int] = collections.Counter()

        for uri, p in profiles.items():
            if uri in skip_set:
                for tag in get_active_tags(p):
                    skip_tag_freq[tag] += 1
                for g in p.get("macro_genres", []):
                    skip_genre_freq[g] += 1
            else:
                for tag in get_active_tags(p):
                    liked_tag_freq[tag] += 1
                for g in p.get("macro_genres", []):
                    liked_genre_freq[g] += 1

        n_skip  = max(len(skip_set), 1)
        n_liked = max(len(liked_set), 1)

        for tag, skip_cnt in skip_tag_freq.items():
            skip_rate  = skip_cnt  / n_skip
            liked_rate = liked_tag_freq.get(tag, 0) / n_liked
            # Disliked: appears in ≥threshold of skip tracks AND skip rate > 3× liked rate
            if skip_rate >= disliked_tag_threshold and liked_rate * 3 < skip_rate:
                disliked_tags.add(tag)

        for genre, skip_cnt in skip_genre_freq.items():
            skip_rate  = skip_cnt  / n_skip
            liked_rate = liked_genre_freq.get(genre, 0) / n_liked
            # Avoided: skip rate > 50% AND skip rate > 4× liked rate
            if skip_rate >= 0.50 and liked_rate * 4 < skip_rate:
                avoided_genres.add(genre)

    return {
        "tag_prefs":      tag_prefs,
        "disliked_tags":  disliked_tags,
        "avoided_genres": avoided_genres,
        "recent_uris":    [],   # populated externally from listening history
    }


# ── Individual signal scores ──────────────────────────────────────────────────

def audio_score(profile: dict, target_vector: list[float]) -> float:
    """
    Gaussian similarity between track's audio vector and mood's audio target.

    Returns 0.0 for tracks with no audio features (neutral [0.5]*6 sentinel).
    Uses Gaussian (RBF) similarity instead of cosine — cosine ignores magnitude
    differences, causing the neutral centroid to score high against all moods.
    """
    v = profile["audio_vector"]
    if _is_neutral_vector(v):
        return 0.0
    return gaussian_similarity(v, target_vector)


def tag_score(profile: dict, expected_tags: list[str]) -> float:
    """
    Weighted overlap between track's mined tags and mood's expected tags.

    Three tiers per expected_tag:
      1. Exact match            → full weight
      2. Substring match        → 0.60×
      3. Synonym cluster match  → 0.45×

    IMPORTANT — each active_tag may satisfy AT MOST ONE expected_tag (the
    highest-scoring one).  Without this guard, a single common tag like
    "angry" would substring-match every mining-generated compound tag
    ("lyr_angry", "angry_sad", "moving_on_angry", "goodbye_angry"…) and
    inflate the score far beyond what that one signal warrants.  Mining
    tags that have no real match in the library become phantom denominators
    that compress all scores into a flat plateau where every track from the
    same genre-artist cluster looks identical.

    lyr_* tags (per-track lyric signals) receive 1.2× weight so they
    differentiate within the same artist when audio features are absent.
    """
    active_tags = get_active_tags(profile)
    if not expected_tags or not active_tags:
        return 0.0

    # M3.1 — Per-track signal confidence.
    # Artist-level fallback tags (no recognised per-track prefix) are
    # downweighted proportionally to how much per-track data already exists.
    # This prevents "Eminem = angry" dominating every mood for every track.
    # Formula: artist_weight_multiplier = max(0.70, 1.0 - confidence)
    # So: confidence=0 → 1.0× (no per-track data, use artist fully)
    #     confidence=0.35 → 0.70× (lyr_* only — moderate discount)
    #     confidence=1.0  → 0.70× (full per-track coverage — floor discount)
    _raw_tags   = profile.get("tags", {})
    _confidence = _signal_confidence(_raw_tags)
    _artist_mult = max(0.70, 1.0 - _confidence) if _confidence > 0 else 1.0

    # Track which active_tags have already been consumed (best-match wins).
    # Key: active_tag name.  Value: best contribution claimed so far.
    claimed: dict[str, float] = {}
    total = 0.0

    for tag in expected_tags:
        _lyr_boost = 1.2 if tag.startswith("lyr_") else 1.0
        # Tier 1 — exact match (doesn't consume; direct value)
        if tag in active_tags:
            _is_per_track = any(tag.startswith(p) for p in _PER_TRACK_PREFIXES)
            _conf_mult = 1.0 if _is_per_track else _artist_mult
            total += active_tags[tag] * _lyr_boost * _conf_mult
            continue
        # Tiers 2 + 3 — find the best unclaimed active_tag for this expected_tag
        best = 0.0
        best_key = ""
        for mined_tag, weight in active_tags.items():
            _mb = 1.2 if mined_tag.startswith("lyr_") else 1.0
            _is_per_track_m = any(mined_tag.startswith(p) for p in _PER_TRACK_PREFIXES)
            _cm = 1.0 if _is_per_track_m else _artist_mult
            candidate = 0.0
            # Token-level substring: "night" matches "night_drive" but not
            # "midnight"; "emo" matches "emo_rap" but not "emotional".
            _tag_toks  = set(tag.split("_"))
            _mine_toks = set(mined_tag.split("_"))
            if _tag_toks & _mine_toks:
                candidate = weight * _mb * _cm * 0.6
            elif _synonym_match(tag, mined_tag):
                candidate = weight * _mb * _cm * 0.45
            # Only consider if better than current best AND better than
            # whatever this active_tag has already contributed elsewhere.
            if candidate > best and candidate > claimed.get(mined_tag, 0.0):
                best = candidate
                best_key = mined_tag
        if best > 0.0:
            claimed[best_key] = best
            total += best

    # M3.2 — Proportional denominator (replaces static cap of 8).
    # Scales with mood complexity: 6-tag mood → denom=3, 27-tag mood → denom=9.
    # Prevents long expected_tag lists from compressing all scores into a flat plateau.
    effective_denom = max(3, len(expected_tags) // 3)
    return min(total / effective_denom, 1.0)


def genre_score(profile: dict, preferred_genres: list[str]) -> float:
    """
    Binary overlap: does any of the track's macro genres match the mood's preferred genres?

    Returns:
      1.0  — a recognized genre matches the mood's preferred genres
      0.3  — ONLY when the track's sole genre is "Other" (truly unknown — could be anything)
      0.0  — track has recognized genres and NONE match (explicit non-match)
      0.5  — mood has no preferred genres at all (neutral pass-through)

    Critical rule: if a track has recognized genres alongside "Other" (e.g. ["Pop", "Other"])
    and NONE of the recognized ones match, we return 0.0 — not 0.3.  "Other" should only
    be a soft wildcard when we have ZERO genre information, not when we know the genre
    and it clearly doesn't fit.
    """
    if not preferred_genres:
        return 0.5
    macros = profile.get("macro_genres") or []
    if not macros:
        return 0.0
    # First pass: hard match
    for macro in macros:
        if macro in preferred_genres:
            return 1.0
    # "Other" wildcard: only applies when it is the ONLY genre we have
    recognized = [m for m in macros if m != "Other"]
    if not recognized:
        return 0.3   # truly unknown — could be anything
    return 0.0       # we know the genre(s) and they don't match


def effective_genre_score(
    profile: dict,
    mood_name: str,
    tag_s: float,
    sem_s: float,
) -> float:
    """
    Genre layer with cross-genre rescue: when macro genres do not match the
    mood's preferred list but tag + semantic evidence is strong, return a
    partial credit so e.g. a sad indie track can still score for Hollow even
    if preferred genres skew toward rap.
    """
    if mood_genre_neutral(mood_name):
        return 0.5
    pref = mood_preferred_genres(mood_name)
    g = genre_score(profile, pref)
    if g > 0.0 or not pref:
        return g
    if sem_s >= 0.38 or tag_s >= 0.14:
        blend = max(sem_s * 0.88, min(1.0, tag_s * 2.4))
        rescue = 0.17 + 0.36 * min(1.0, blend)
        return min(0.52, rescue)
    return 0.0


def semantic_score(profile: dict, mood_name: str) -> float:
    """
    Semantic dimension overlap between a track's expanded tag profile and
    the mood's declared semantic core.

    This operates at the MEANING layer — above raw tag names, below audio:
      • A track tagged "late_night_drive" expands to dims: night, dark, drive,
        introspective (via SEMANTIC_MAP in playlist_mining.py).
      • A track tagged "phonk" expands to: dark, drive, night, anger (BASIC_MAP).
      • The mood "Late Night Drive" declares semantic_core: [night, dark, drive,
        introspective, atmospheric, cinematic].
      • Overlap is computed as weighted dot product, normalised by mood core weight.

    This catches tracks that fit the mood's meaning even when they lack the
    exact playlist-style expected tags ("night_drive", "2am", etc.).

    Returns:
      0.0  — no semantic overlap (or track has no tag data)
      0.5  — neutral fallback when mood has no semantic core defined
      1.0  — full overlap

    Unlike tag_score which matches specific playlist keywords, semantic_score
    matches the mood's abstract identity dimensions.  Together they cover both
    surface (what playlists called it) and meaning (what it actually is).
    """
    sem_core = mood_semantic_core(mood_name)
    if not sem_core:
        return 0.5  # neutral — mood has no declared semantic core yet

    track_tags = get_active_tags(profile)
    if not track_tags:
        return 0.0

    from core.profile import _TAG_TO_CLUSTER  # noqa: PLC0415

    weighted_overlap = 0.0
    for dim, mood_weight in sem_core.items():
        if dim in track_tags:
            weighted_overlap += track_tags[dim] * mood_weight
        else:
            # Cluster resolution: dim may be a cluster MEMBER, not a cluster name.
            # e.g. "peaceful" → "calm", "worship" → "spiritual", "atmospheric" → "ambient"
            # Use the same inverted-lookup table that collapse_tags uses.
            cluster = _TAG_TO_CLUSTER.get(dim)
            if cluster and cluster in track_tags:
                weighted_overlap += track_tags[cluster] * mood_weight * 0.9
            else:
                # lyr_* prefix expansion: "lyr_dark" satisfies the "dark" semantic dimension.
                # Lyrics-derived mood signals are real but slightly less reliable than direct tags.
                lyr_key = "lyr_" + dim
                if lyr_key in track_tags:
                    weighted_overlap += track_tags[lyr_key] * mood_weight * 0.85

    max_possible = sum(sem_core.values())
    if max_possible == 0:
        return 0.0
    return min(weighted_overlap / max_possible, 1.0)


def user_preference_boost(profile: dict, user_audio_mean: list[float]) -> float:
    """
    Boost tracks that are close to the user's overall library taste.
    Returns a multiplier between 0.85 and 1.15.

    Uses Gaussian similarity so neutral-vector tracks don't get an inflated
    boost from their accidental proximity to a neutral library mean.
    """
    v = profile["audio_vector"]
    if _is_neutral_vector(v):
        return 1.0  # no boost / no penalty for tracks without features
    sim = gaussian_similarity(v, user_audio_mean)
    # Map [0,1] similarity to [0.85, 1.15] boost
    return 0.85 + (sim * 0.30)


# ── Combined score ─────────────────────────────────────────────────────────────

def score_track(
    profile: dict,
    mood_name: str,
    user_audio_mean: list[float] | None = None,
    user_tag_prefs: dict[str, float] | None = None,
    weights: tuple[float, float, float, float] = (W_METADATA_AUDIO, W_TAGS, W_SEMANTIC, W_GENRE),
    penalty_cap: float = 0.75,
    merged_expected_tags: list[str] | None = None,
) -> float:
    """
    Compute the full multi-signal score for a track against a mood.

    Four signal layers:
      audio    — how close the track's audio features are to the mood's target
      tags     — how many of the mood's expected playlist tags the track has
      semantic — how many of the mood's identity dimensions the track covers
      genre    — whether the track's genre matches the mood's preferred genres

    Scoring pipeline (in order):
      1. Hard audio constraints  — energy / valence bounds (binary reject)
      2. Four-signal weighted base score
      3. Positive match boost    — reward strong expected-tag overlap (+up to 15%)
      4. Negative signal penalty — forbidden tags/genres reduce score (proportional)
      5. Conflict penalty        — intra-track contradictions reduce score
      6. User preference boost   — proximity to user's audio taste centroid
      7. Taste adaptation boost  — alignment with user's tag preferences

    Args:
        profile:      Track profile dict from profile.build().
        mood_name:    Target mood name.
        user_audio_mean: Library audio centroid from profile.user_audio_mean().
        user_tag_prefs:  Tag preference map from profile.user_tag_preferences().
        weights:      (w_audio, w_tags, w_semantic, w_genre) — must sum to 1.0.
        penalty_cap:  Max penalty from forbidden filters (0.75 default;
                      pass 0.45 for MVP / thin-playlist mode).
        merged_expected_tags: Optional list from combine_expected_tags(); overrides
            static mood expected_tags for tag layer and positive_boost.

    Returns:
        Float in roughly [0, 1], or -1.0 if hard audio constraints reject
        the track (caller treats -1.0 as "do not include").
    """
    if not passes_hard_filters(profile, mood_name):
        return -1.0

    w_audio, w_tags, w_semantic, w_genre = effective_score_weights(
        profile, resolved_score_weights(weights),
    )
    target_vec  = mood_audio_target(mood_name)
    exp_tags    = merged_expected_tags if merged_expected_tags is not None else mood_expected_tags(mood_name)
    pref_genres = mood_preferred_genres(mood_name)

    a = audio_score(profile, target_vec)
    t = tag_score(profile, exp_tags)
    if mood_lyric_focus(mood_name):
        lw = float(getattr(_cfg, "SCAN_LYRIC_WEIGHT", 1.0) or 1.0)
        if lw > 1.01 and any(k.startswith("lyr_") for k in get_active_tags(profile)):
            t = min(1.0, t * min(lw, 1.48))

    # Graph agreement boost — graph_mood_<slug> is a direct mood identifier.
    # A track adjacent to anchors for this mood should contribute that
    # confidence as a floor on the tag score, since the graph_mood tag
    # does not token-match against expected_tags (different vocabulary).
    _g_slug  = mood_name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    while "__" in _g_slug:
        _g_slug = _g_slug.replace("__", "_")
    _g_slug = _g_slug.strip("_")
    _g_conf  = get_active_tags(profile).get(f"graph_mood_{_g_slug}", 0.0)
    if _g_conf > 0.0:
        t = max(t, _g_conf)  # graph signal acts as floor — never reduces existing tag score

    s = semantic_score(profile, mood_name)
    g = effective_genre_score(profile, mood_name, t, s)

    base = w_audio * a + w_tags * t + w_semantic * s + w_genre * g

    # Positive match boost — rewards perfect expected-tag overlap
    base *= positive_boost(profile, mood_name, exp_tags)

    # Proportional forbidden-signal penalty
    penalty = negative_filter_penalty(profile, mood_name, penalty_cap)
    if penalty > 0:
        base *= (1.0 - penalty)

    # Intra-track conflict penalty (mood-independent self-contradiction)
    cp = conflict_penalty(profile)
    if cp > 0:
        base *= (1.0 - cp)

    if user_audio_mean:
        base *= user_preference_boost(profile, user_audio_mean)
    if user_tag_prefs:
        base *= taste_adaptation_boost(profile, user_tag_prefs)

    base *= user_model_score_multiplier(profile)

    return round(base, 6)


def rank_tracks(
    profiles: dict[str, dict],
    mood_name: str,
    user_audio_mean: list[float] | None = None,
    user_tag_prefs: dict[str, float] | None = None,
    min_score: float = 0.25,
    weights: tuple[float, float, float, float] = (W_METADATA_AUDIO, W_TAGS, W_SEMANTIC, W_GENRE),
    min_playlist_size: int = 15,
    allow_mvp_fallback: bool = True,
    mvp_score_floor: float | None = None,
    merged_expected_tags: list[str] | None = None,
) -> list[tuple[str, float]]:
    """
    Score all tracks for a given mood, with automatic MVP fallback.

    Pipeline:
      1. Hard audio filter     — energy / valence bounds (binary reject)
      2. Weighted forbidden penalty — reduces scores, not a hard gate
      3. Score threshold       — min_score
      4. Confidence gate       — reject tracks with no tag + no genre signal
      5. Sort descending
      6. MVP fallback          — if result < min_playlist_size, re-score
         with softer penalty cap (0.45) and lower score floor (0.15)
         so thin moods still produce a playable playlist

    Args:
        profiles:          {uri: profile} from profile.build_all().
        mood_name:         Target mood name.
        user_audio_mean:   Library audio centroid.
        user_tag_prefs:    User tag preferences.
        min_score:         Score floor for standard pass (default 0.25).
        weights:           (w_audio, w_tags, w_genre).
        min_playlist_size: If fewer tracks survive standard scoring, trigger
                           MVP fallback to ensure a usable result.
        allow_mvp_fallback: If False, skip the relaxed MVP pass (strict mode).
        mvp_score_floor:   Score floor for MVP pass; default max(0.15, min_score*0.6).
        merged_expected_tags: Static + mining merged expected tags for scoring.

    Returns [(uri, score), ...] sorted by score descending.
    """
    exp_tags    = merged_expected_tags if merged_expected_tags is not None else mood_expected_tags(mood_name)
    pref_genres = mood_preferred_genres(mood_name)
    _mvp_floor = (
        mvp_score_floor
        if mvp_score_floor is not None
        else max(0.15, min_score * 0.6)
    )

    def _score_pass(
        penalty_cap: float,
        score_floor: float,
        confidence_floor: float,
    ) -> list[tuple[str, float]]:
        result = []
        for uri, profile in profiles.items():
            s = score_track(
                profile, mood_name, user_audio_mean, user_tag_prefs, weights,
                penalty_cap=penalty_cap,
                merged_expected_tags=merged_expected_tags,
            )
            if s < 0:           # hard audio constraint reject
                continue
            if s < score_floor:
                continue

            # ── Confidence gate ──────────────────────────────────────────
            conf     = profile.get("confidence", {})
            tag_conf = conf.get("tags", 1.0)
            t        = tag_score(profile, exp_tags)
            sem_g    = semantic_score(profile, mood_name)
            g        = effective_genre_score(profile, mood_name, t, sem_g)

            if tag_conf < confidence_floor and g < 0.50:
                continue
            if t < 0.05 and g < 0.20 and sem_g < 0.22:
                continue

            result.append((uri, s))
        result.sort(key=lambda x: -x[1])
        return result

    # ── Standard pass ─────────────────────────────────────────────────────────
    scored = _score_pass(
        penalty_cap=0.75,
        score_floor=min_score,
        confidence_floor=0.10,
    )

    # ── MVP fallback — relax filters if playlist is too thin ──────────────────
    if allow_mvp_fallback and len(scored) < min_playlist_size:
        mvp = _score_pass(
            penalty_cap=0.45,   # softer forbidden penalty
            score_floor=_mvp_floor,
            confidence_floor=0.05,
        )
        # Keep the higher-scoring of the two passes for tracks in both
        uri_in_standard = {uri for uri, _ in scored}
        extras = [(uri, s) for uri, s in mvp if uri not in uri_in_standard]
        scored = sorted(scored + extras, key=lambda x: -x[1])

    return scored


# ── Multi-signal cohesion filter ──────────────────────────────────────────────

def _tag_jaccard(tags_a: dict, tags_b: set) -> float:
    """Jaccard similarity between a track's tag set and a centroid tag set.

    Empty vs empty returns 0.0, not 1.0 — two tagless tracks share no signal,
    so treating them as 'maximally similar' would let all empty-tag tracks pass
    the cohesion filter as a coherent cluster even when they are totally random.
    """
    a = set(tags_a.keys())
    if not a or not tags_b:
        return 0.0   # no shared information → no cohesion
    return len(a & tags_b) / len(a | tags_b)


def cohesion_filter(
    scored: list[tuple[str, float]],
    profiles: dict[str, dict],
    mood_name: str = "",
    threshold: float | None = None,
    audio_weight: float = 0.40,
    tag_weight: float = 0.30,
    semantic_weight: float = 0.30,
) -> list[tuple[str, float]]:
    """
    Remove tracks too far from the playlist's three-signal centroid.

    Three-signal cohesion (0.40 audio + 0.30 tag + 0.30 semantic):

      Audio cohesion
        Gaussian similarity to the mean audio vector of the playlist.
        Tracks without real audio features pass automatically (no data = no penalty).

      Tag cohesion
        Jaccard similarity to the dominant tag cloud (tags in ≥30% of tracks).
        Catches genre drift and surface-level vibe mismatch.

      Semantic cohesion
        Overlap between the track's expanded tag dimensions and the playlist's
        semantic centroid (dimensions present in ≥40% of tracks).
        Catches subtle emotional inconsistency that tag Jaccard misses.
        Falls back to 1.0 if the playlist has no common semantic dimensions.

    Tracks below ``threshold`` are removed.  The combined three-signal check
    prevents audio outliers (audio cohesion), playlist name drift (tag cohesion),
    and emotional inconsistency (semantic cohesion) simultaneously.

    Args:
        scored:          Output of rank_tracks — [(uri, score), ...].
        profiles:        Full profile dict {uri: profile}.
        mood_name:       Target mood (used to anchor semantic centroid).
        threshold:       Min combined cohesion to keep.  Default 0.35.
        audio_weight:    Weight of audio cohesion component.
        tag_weight:      Weight of tag cohesion component.
        semantic_weight: Weight of semantic cohesion component.

    Returns:
        Filtered [(uri, score), ...] in the same order.
    """
    if len(scored) < 4:
        return scored

    # Resolve threshold: if not supplied, adapt to playlist size
    if threshold is None:
        threshold = adaptive_threshold(len(scored))

    # ── Audio centroid ────────────────────────────────────────────────────────
    real_vecs = [
        profiles[uri]["audio_vector"]
        for uri, _ in scored
        if not _is_neutral_vector(profiles[uri]["audio_vector"])
    ]
    audio_centroid = None
    if real_vecs:
        dim = len(real_vecs[0])
        n   = len(real_vecs)
        audio_centroid = [sum(v[i] for v in real_vecs) / n for i in range(dim)]

    # ── Tag centroid (dominant tags: present in ≥30% of tracks) ──────────────
    tag_counts: dict[str, int] = collections.Counter()
    for uri, _ in scored:
        for tag in get_active_tags(profiles[uri]):
            tag_counts[tag] += 1
    n_total = len(scored)
    tag_centroid = {tag for tag, cnt in tag_counts.items() if cnt / n_total >= 0.30}

    # ── Semantic centroid (dims present in ≥40% of tracks) ───────────────────
    # Use the mood's semantic core as anchor, intersected with dims found in
    # the actual playlist tracks so the centroid stays grounded in real data.
    sem_counts: dict[str, int] = collections.Counter()
    for uri, _ in scored:
        for dim in get_active_tags(profiles[uri]):
            sem_counts[dim] += 1
    sem_centroid = {
        dim for dim, cnt in sem_counts.items()
        if cnt / n_total >= 0.40
        and (not mood_name or dim in mood_semantic_core(mood_name))
    }
    # Fallback: if intersection is empty, use any dims at ≥40% presence
    if not sem_centroid:
        sem_centroid = {dim for dim, cnt in sem_counts.items() if cnt / n_total >= 0.40}

    # ── Filter ────────────────────────────────────────────────────────────────
    result = []
    for uri, score in scored:
        v = profiles[uri]["audio_vector"]

        # Audio similarity
        if audio_centroid and not _is_neutral_vector(v):
            a_sim = gaussian_similarity(v, audio_centroid)
        else:
            a_sim = 1.0  # no audio data — cannot penalise

        # Tag similarity (surface: playlist name overlap)
        track_tags = get_active_tags(profiles[uri])
        if tag_centroid:
            t_sim = _tag_jaccard(track_tags, tag_centroid)
        else:
            t_sim = 1.0  # no centroid tags — cannot penalise

        # Semantic similarity (meaning layer: dimension overlap)
        if sem_centroid:
            track_sem = set(track_tags.keys())
            sem_overlap = len(track_sem & sem_centroid)
            s_sim = sem_overlap / len(sem_centroid)
        else:
            s_sim = 1.0  # no semantic centroid — cannot penalise

        combined = audio_weight * a_sim + tag_weight * t_sim + semantic_weight * s_sim
        if combined >= threshold:
            result.append((uri, score))

    return result


# ── Identity separation (cross-mood deduplication) ───────────────────────────

def dedup_across_moods(
    mood_ranked: dict[str, list[tuple[str, float]]],
    win_margin: float = 0.15,
) -> dict[str, list[tuple[str, float]]]:
    """
    Reduce overlap between mood playlists so they feel distinct.

    For every track that appears in multiple moods, it is kept only in the
    mood where its score is highest — but ONLY if that score is at least
    ``win_margin`` higher than the next-best mood.  When moods are closely
    matched (scores within win_margin), the track stays in all of them,
    because genuine multi-mood tracks should not be arbitrarily reassigned.

    This prevents the "Late Night Drive" and "Overthinking" playlists from
    being 60% identical while still allowing naturally cross-cutting tracks
    (e.g. a melancholic R&B track that fits several moods) to appear in both.

    Args:
        mood_ranked: {mood_name: [(uri, score), ...]} from rank_tracks.
        win_margin:  Score advantage the winner needs to claim exclusive
                     ownership.  Default 0.15 (15 percentage points).

    Returns:
        {mood_name: [(uri, score), ...]} with overlapping tracks removed from
        non-dominant moods.  Sort order preserved within each mood.
    """
    # Build track → {mood: score}
    track_scores: dict[str, dict[str, float]] = collections.defaultdict(dict)
    for mood, ranked in mood_ranked.items():
        for uri, score in ranked:
            track_scores[uri][mood] = score

    # Determine which moods "own" each track
    # Dynamic margin: similar moods require a larger gap to claim a track.
    # Prevents Late Night Drive / Overthinking from being virtually identical.
    owned_by: dict[str, set[str]] = {}  # uri → set of moods that keep it
    for uri, ms in track_scores.items():
        if len(ms) == 1:
            owned_by[uri] = set(ms.keys())
            continue
        best_mood  = max(ms, key=ms.get)
        best_score = ms[best_mood]

        # Check if best mood beats EVERY competitor by its dynamic margin
        is_clear = True
        for other_mood, other_score in ms.items():
            if other_mood == best_mood:
                continue
            # Similar moods → higher required margin (up to win_margin * 2)
            sem_sim = mood_semantic_similarity(best_mood, other_mood)
            required = win_margin + sem_sim * win_margin  # [margin, 2×margin]
            if best_score - other_score < required:
                is_clear = False
                break

        if is_clear:
            owned_by[uri] = {best_mood}     # winner takes it
        else:
            owned_by[uri] = set(ms.keys())  # contested → keep in all

    # Rebuild playlists
    result: dict[str, list[tuple[str, float]]] = {}
    for mood, ranked in mood_ranked.items():
        result[mood] = [
            (uri, score)
            for uri, score in ranked
            if mood in owned_by.get(uri, {mood})
        ]

    return result


# ── Playlist confidence score ─────────────────────────────────────────────────

def playlist_confidence(
    scored: list[tuple[str, float]],
    profiles: dict[str, dict],
    mood_name: str,
) -> dict:
    """
    Score how confident we are in the quality of a generated playlist.

    Three components:
      cohesion_score       — how similar tracks are to each other (audio + tag)
      avg_track_confidence — mean profile.confidence.overall across all tracks
      tag_consistency      — fraction of tracks sharing the playlist's mode tags
                             (tags that appear in ≥50% of included tracks)

    Combined: cohesion * 0.40 + avg_confidence * 0.30 + tag_consistency * 0.30

    Thresholds (rough guide):
      ≥ 0.70 — strong playlist, high signal quality
      0.50–0.70 — decent playlist, worth offering
      < 0.50 — weak signal, warn user or flag for review

    Returns:
      {
        "cohesion":        float,   — audio centroid similarity
        "avg_confidence":  float,   — mean track data quality
        "tag_consistency": float,   — tag agreement across tracks
        "overall":         float,   — weighted combination
      }
    """
    if not scored:
        return {
            "cohesion": 0.0, "avg_confidence": 0.0,
            "tag_consistency": 0.0, "overall": 0.0,
        }

    n = len(scored)

    # ── Average track confidence ──────────────────────────────────────────────
    avg_conf = sum(
        profiles[uri].get("confidence", {}).get("overall", 0.5)
        for uri, _ in scored
    ) / n

    # ── Tag consistency ───────────────────────────────────────────────────────
    # Measure how much tracks agree on tags (mode tags = present in ≥50%)
    tag_counts: dict[str, int] = collections.Counter()
    for uri, _ in scored:
        for tag in get_active_tags(profiles[uri]):
            tag_counts[tag] += 1
    mode_tags = {tag for tag, cnt in tag_counts.items() if cnt / n >= 0.50}
    if mode_tags:
        tracks_with_mode = sum(
            1 for uri, _ in scored
            if any(t in get_active_tags(profiles[uri]) for t in mode_tags)
        )
        tag_consistency = tracks_with_mode / n
    else:
        tag_consistency = 0.4  # no dominant tags — below neutral (sparse signal)

    # ── Audio cohesion ────────────────────────────────────────────────────────
    real_vecs = [
        profiles[uri]["audio_vector"]
        for uri, _ in scored
        if not _is_neutral_vector(profiles[uri]["audio_vector"])
    ]
    if len(real_vecs) >= 2:
        dim = len(real_vecs[0])
        centroid = [
            sum(v[i] for v in real_vecs) / len(real_vecs) for i in range(dim)
        ]
        cohesion = sum(
            gaussian_similarity(v, centroid) for v in real_vecs
        ) / len(real_vecs)
    else:
        cohesion = 0.5  # not enough audio data to measure

    overall = round(
        cohesion * 0.40 + avg_conf * 0.30 + tag_consistency * 0.30,
        4,
    )
    return {
        "cohesion":        round(cohesion, 4),
        "avg_confidence":  round(avg_conf, 4),
        "tag_consistency": round(tag_consistency, 4),
        "overall":         overall,
    }


# ── Track explanation ─────────────────────────────────────────────────────────

def explain(profile: dict, mood_name: str) -> dict:
    """
    Generate a structured explanation for a track's fit (or rejection) for a mood.

    Returns:
      {
        "fits":    [str, ...]  — signals that support inclusion
        "flags":   [str, ...]  — soft concerns (won't reject but noted)
        "penalty": float       — weighted forbidden-signal penalty applied
        "score":   float       — final score (0 if track would be rejected)
      }

    Examples:
      fits:  ["night + introspective (tag match 68%)", "genre: Hip-Hop / R&B"]
      flags: ["contains 'party' tag (−25% penalty applied)"]
    """
    target_vec  = mood_audio_target(mood_name)
    exp_tags    = mood_expected_tags(mood_name)
    pref_genres = mood_preferred_genres(mood_name)

    a_score  = audio_score(profile, target_vec)
    t_score  = tag_score(profile, exp_tags)
    s_score  = semantic_score(profile, mood_name)
    g_score  = effective_genre_score(profile, mood_name, t_score, s_score)
    penalty  = negative_filter_penalty(profile, mood_name)

    fits:  list[str] = []
    flags: list[str] = []

    # ── Fit signals ───────────────────────────────────────────────────────────
    if a_score > 0.05 and profile.get("audio_vector_source") == "metadata_proxy":
        fits.append(f"metadata audio proxy ({a_score:.0%} vs mood target)")

    _explain_tags = get_active_tags(profile)
    if t_score > 0.08 and _explain_tags:
        top = sorted(_explain_tags.items(), key=lambda x: -x[1])[:4]
        # Highlight which tags overlap with expected
        exp_set = set(exp_tags)
        matched = [
            t for t, _ in top
            if t in exp_set or any(
                t in et or et in t or _synonym_match(et, t) for et in exp_set
            )
        ]
        all_top = [t for t, _ in top]
        label = " + ".join(matched[:3]) if matched else " + ".join(all_top[:3])
        fits.append(f"tags: {label} ({t_score:.0%})")

    if s_score > 0.08 and s_score != 0.5:  # skip neutral fallback
        sem_core = mood_semantic_core(mood_name)
        track_tags = get_active_tags(profile)
        matched_dims = sorted(
            [dim for dim in sem_core if dim in track_tags],
            key=lambda d: -track_tags[d],
        )[:4]
        if matched_dims:
            fits.append(f"semantic: {' + '.join(matched_dims)} ({s_score:.0%})")

    if genre_score(profile, pref_genres) >= 1.0 and profile.get("macro_genres"):
        fits.append("genre: " + ", ".join(profile["macro_genres"][:2]))
    elif g_score > 0.15 and (t_score >= 0.12 or s_score >= 0.30):
        fits.append(
            f"cross-genre fit ({g_score:.0%} genre layer — strong tag/semantic match)"
        )

    if not fits:
        if t_score > 0.05 or g_score > 0.0:
            fits.append("weak tag/genre match")

    # ── Soft flags (forbidden signal degradation) ─────────────────────────────
    if penalty > 0:
        forbidden_t = mood_forbidden_tags(mood_name)
        forbidden_g = mood_forbidden_genres(mood_name)
        track_tags  = set(get_active_tags(profile).keys())
        macro_genres = set(profile.get("macro_genres", []))

        for ft in forbidden_t:
            for tt in track_tags:
                if tt == ft or tt.startswith(ft) or ft.startswith(tt):
                    flags.append(f"contains '{tt}' tag (-25% penalty)")
                    break
        for fg in forbidden_g:
            if fg in macro_genres:
                flags.append(f"genre '{fg}' conflicts with mood (-35% penalty)")
                break

    # ── Hard rejection check ──────────────────────────────────────────────────
    if not passes_hard_filters(profile, mood_name):
        features = profile.get("_features") or {}
        constraints = {}
        from core.mood_graph import mood_audio_constraints
        constraints = mood_audio_constraints(mood_name)
        energy  = features.get("energy", None)
        valence = features.get("valence", None)
        detail_parts = []
        if energy is not None and "energy_max" in constraints and energy > constraints["energy_max"]:
            detail_parts.append(f"energy {energy:.2f} > max {constraints['energy_max']}")
        if energy is not None and "energy_min" in constraints and energy < constraints["energy_min"]:
            detail_parts.append(f"energy {energy:.2f} < min {constraints['energy_min']}")
        if valence is not None and "valence_max" in constraints and valence > constraints["valence_max"]:
            detail_parts.append(f"valence {valence:.2f} > max {constraints['valence_max']}")
        if valence is not None and "valence_min" in constraints and valence < constraints["valence_min"]:
            detail_parts.append(f"valence {valence:.2f} < min {constraints['valence_min']}")
        rejection = "audio constraints: " + "; ".join(detail_parts) if detail_parts else "audio out of range"
        return {"fits": [], "flags": flags, "penalty": penalty, "score": 0.0, "rejected": rejection}

    w_a, w_t, w_s, w_g = effective_score_weights(
        profile, resolved_score_weights((W_METADATA_AUDIO, W_TAGS, W_SEMANTIC, W_GENRE)),
    )
    final_score = round(
        (w_a * a_score + w_t * t_score + w_s * s_score + w_g * g_score)
        * (1.0 - penalty),
        4,
    )
    return {
        "fits":    fits,
        "flags":   flags,
        "penalty": round(penalty, 4),
        "score":   final_score,
        "rejected": None,
    }


# ── Refinement loop ───────────────────────────────────────────────────────────

def refine_playlist(
    ranked: list[tuple[str, float]],
    threshold: float = 0.65,
    max_passes: int = 2,
    drop_ratio: float = 0.10,
) -> list[tuple[str, float]]:
    """
    Iteratively drop the bottom drop_ratio of tracks until avg score meets threshold.

    Stops early if playlist has fewer than 15 tracks (safety guard for small
    libraries), after max_passes, or when avg >= threshold.

    Args:
        ranked:     [(uri, score), ...] sorted descending.
        threshold:  Target average score.  Default 0.65.
        max_passes: Maximum refinement iterations.
        drop_ratio: Fraction to drop per pass (default 0.10 = bottom 10%).

    Returns:
        Refined [(uri, score), ...].
    """
    result = list(ranked)
    if len(result) < 15:   # safety: never prune small playlists
        return result
    for _ in range(max_passes):
        if len(result) < 15:
            break
        avg = sum(s for _, s in result) / len(result)
        if avg >= threshold:
            break
        cut = max(1, int(len(result) * drop_ratio))
        result = result[:-cut]
    return result


def enforce_artist_diversity(
    ranked: list[tuple[str, float]],
    profiles: dict[str, dict],
    max_per_artist: int = 3,
    hard_cap: int | None = None,
) -> list[tuple[str, float]]:
    """
    Apply score decay to repeated artists rather than hard-capping.

    Without audio features, tag-based scoring gives every track from the same
    artist nearly identical scores. A hard cap forces in off-mood tracks from
    other artists. Score decay instead penalises repeated tracks enough for
    better-fitting alternatives to surface naturally, while the best mood-
    matching tracks from any artist still earn their position.

    Decay schedule (applied on top of original score, then re-sorted):
      appearance 1-max_per_artist  → no decay
      appearance max_per_artist+1  → ×0.75
      appearance max_per_artist+2  → ×0.55
      appearance max_per_artist+3+ → ×0.38

    hard_cap: absolute ceiling per artist regardless of score (default 6).
    """
    if not ranked or max_per_artist <= 0:
        return ranked

    _hard = hard_cap if hard_cap is not None else max_per_artist + 1

    def _artist_key(uri: str) -> str:
        p = profiles.get(uri, {})
        artists = p.get("artists") or []
        if artists:
            a = artists[0]
            return str(a).lower() if a else uri
        return uri

    artist_counts: dict[str, int] = {}
    decayed: list[tuple[str, float]] = []

    for uri, sc in ranked:
        key = _artist_key(uri)
        cnt = artist_counts.get(key, 0)
        if cnt >= _hard:
            continue  # hard ceiling only
        artist_counts[key] = cnt + 1
        overflow = cnt - (max_per_artist - 1)
        if overflow <= 0:
            decayed.append((uri, sc))
        elif overflow == 1:
            decayed.append((uri, sc * 0.75))
        elif overflow == 2:
            decayed.append((uri, sc * 0.55))
        else:
            decayed.append((uri, sc * 0.38))

    # Re-sort after decay so the best mood-fit track wins regardless of artist
    decayed.sort(key=lambda x: -x[1])
    return decayed


def ensure_minimum(
    ranked: list[tuple[str, float]],
    all_ranked: list[tuple[str, float]],
    min_tracks: int = 20,
    min_score: float = 0.15,
    strict_backfill: bool = True,
    mood_name: str | None = None,
    profiles: dict[str, dict] | None = None,
    backfill_expected_tags: list[str] | None = None,
) -> list[tuple[str, float]]:
    """
    Backfill ranked playlist to min_tracks from all_ranked if below threshold.

    Only adds tracks scoring above a proportional floor (min_score * 0.5, minimum
    0.05) so backfill stays mood-consistent even with weak signal.

    Args:
        ranked:     Current playlist [(uri, score), ...].
        all_ranked: Full scored pool to backfill from, sorted descending.
        min_tracks: Target minimum playlist size (0 disables backfill).
        min_score:  The scoring threshold used in the main pass; backfill
                    uses 50% of this (M3.2) so it's relaxed but not garbage.
        strict_backfill: If True and mood_name+profiles set, skip backfill
            candidates with very weak tag and semantic fit.
        mood_name:    Mood id for semantic/tag backfill gate.
        profiles:     Track profiles for backfill gate.
        backfill_expected_tags: Tag list for tag_score during gate (defaults to mood).

    Returns:
        Extended [(uri, score), ...].
    """
    if min_tracks <= 0 or len(ranked) >= min_tracks:
        return ranked
    existing = {uri for uri, _ in ranked}
    floor = max(min_score * 0.5, 0.05)
    exp_for_gate = (
        backfill_expected_tags
        if backfill_expected_tags is not None
        else (mood_expected_tags(mood_name) if mood_name else [])
    )
    extras: list[tuple[str, float]] = []
    for uri, s in all_ranked:
        if uri in existing or s <= floor:
            continue
        if strict_backfill and mood_name and profiles:
            p = profiles.get(uri)
            if p:
                te = tag_score(p, exp_for_gate) if exp_for_gate else 0.0
                sem = semantic_score(p, mood_name)
                if te < 0.04 and sem < 0.12:
                    continue
        extras.append((uri, s))
    needed = min_tracks - len(ranked)
    return ranked + extras[:needed]


# ── Hybrid expected-tag builder ───────────────────────────────────────────────

def combine_expected_tags(
    mood_name: str,
    observed_tags: dict[str, float],
    observed_weight: float = 0.30,
) -> list[str]:
    """
    Merge static mood expected_tags with observed playlist-mining tags.

    Static tags define the mood's identity; observed tags (mined from real
    playlists) add data-driven grounding.  The observed set is blended at
    observed_weight so it enriches but does not override the static definition.

    Args:
        mood_name:       Target mood name.
        observed_tags:   {tag: weight} from playlist mining results.
        observed_weight: Scale factor for observed tags when merged.

    Returns:
        Merged list of tag strings (deduped, static tags listed first).
    """
    static = list(mood_expected_tags(mood_name) or [])
    static_set = set(static)
    for _lt in mood_lyrical_expected_tags(mood_name):
        if _lt not in static_set:
            static.append(_lt)
            static_set.add(_lt)

    # Blend top observed tags not already in static.
    # Exclude numeric pseudo-tags (dz_bpm, vader_valence) — these accumulate
    # raw floats (BPM values) during mining, producing inflated observed weights
    # that have no place in a tag-match expected list.
    _NUMERIC_PSEUDO = frozenset({"dz_bpm", "vader_valence"})
    top_observed = sorted(observed_tags.items(), key=lambda x: -x[1])
    n_to_add = max(2, int(len(static) * observed_weight))
    extras = [
        tag for tag, _ in top_observed
        if tag not in static_set and tag not in _NUMERIC_PSEUDO
    ][:n_to_add]

    return static + extras


# ── Cross-mood dominance check ────────────────────────────────────────────────

def enforce_dominance(
    all_mood_scores: dict[str, float],
    margin: float = 0.15,
) -> str | None:
    """
    Return the winning mood only if it leads second place by >= margin.

    When two moods score within the margin, the track is ambiguous and
    this returns None — callers may leave it in both playlists.

    Args:
        all_mood_scores: {mood_name: score} for one track across all moods.
        margin:          Required gap between first and second place.

    Returns:
        Winning mood name, or None if ambiguous.
    """
    if not all_mood_scores:
        return None
    sorted_moods = sorted(all_mood_scores.items(), key=lambda x: -x[1])
    best_name, best_score = sorted_moods[0]
    if len(sorted_moods) < 2:
        return best_name
    _, second_score = sorted_moods[1]
    if best_score - second_score >= margin:
        return best_name
    return None


# ── Query / feedback boosts ───────────────────────────────────────────────────

def query_boost(
    profile: dict,
    include_tags: list[str],
    strength: float = 0.20,
) -> float:
    """
    Score boost for tracks matching user-specified search tags.

    Args:
        profile:      Track profile dict.
        include_tags: Tags the user explicitly wants to include.
        strength:     Maximum additive boost.  Default 0.20.

    Returns:
        Float additive boost in [0.0, strength].
    """
    if not include_tags:
        return 0.0
    track_tags = get_active_tags(profile)
    if not track_tags:
        return 0.0
    hits = sum(track_tags.get(t, 0.0) for t in include_tags)
    return round(min(hits / len(include_tags) * strength, strength), 6)


def user_feedback_boost(
    profile: dict,
    preferred_tags: list[str],
    strength: float = 0.10,
) -> float:
    """
    Small additive boost for tracks matching the user's preferred tag history.

    Args:
        profile:        Track profile dict.
        preferred_tags: Tags the user has responded positively to over time.
        strength:       Maximum additive boost.  Default 0.10.

    Returns:
        Float additive boost in [0.0, strength].
    """
    if not preferred_tags:
        return 0.0
    track_tags = get_active_tags(profile)
    if not track_tags:
        return 0.0
    hits = sum(1 for t in preferred_tags if t in track_tags)
    return round(min(hits / len(preferred_tags) * strength, strength), 6)


# ── Export confidence gate ────────────────────────────────────────────────────

def passes_confidence_gate(
    ranked: list[tuple[str, float]],
    profiles: dict[str, dict],
    mood_name: str,
    threshold: float = 0.55,
) -> tuple[bool, float]:
    """
    Check whether a playlist meets the minimum confidence bar for export.

    Uses playlist_confidence().overall and returns (passes, score).
    Callers should warn or block export when passes is False.

    Args:
        ranked:    [(uri, score), ...] from rank_tracks / cohesion_filter.
        profiles:  Full profile dict {uri: profile}.
        mood_name: Target mood name.
        threshold: Minimum overall confidence.  Default 0.55.

    Returns:
        (bool passes, float confidence_score)
    """
    conf = playlist_confidence(ranked, profiles, mood_name)
    score = conf.get("overall", 0.0)
    return score >= threshold, score
