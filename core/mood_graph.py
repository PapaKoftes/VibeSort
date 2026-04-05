"""
mood_graph.py — Load mood pack definitions and provide fuzzy matching.

The mood graph connects moods to each other so that:
  - "late night drive" relates to "overthinking" and "hollow"
  - "overflow" relates to "pre-game" and "adrenaline"

This enables fuzzy vibe matching: user types "something dark and floaty"
and we can find the closest packs.

Semantic system
---------------
Each mood has a `semantic_core` — a set of atomic emotional/contextual
dimensions that define its identity (e.g. LND = night + dark + introspective).
These dimensions form a shared vocabulary across moods and tracks, enabling
a higher-level "what is this about" comparison beyond raw tag matching.

The full SEMANTIC_DIMENSIONS vocabulary (~60 terms) defines the space.
Tracks acquire semantic dimensions through playlist_mining expansion.
Moods declare them explicitly in packs.json under `semantic_core`.
"""

import json
import os
import math


# ── Semantic dimension vocabulary ─────────────────────────────────────────────
# All atomic concepts that form the shared semantic space between tracks
# and moods.  Tracks acquire these via BASIC_MAP / SEMANTIC_MAP expansion
# in playlist_mining.py.  Moods declare them in packs.json `semantic_core`.
#
# These are deliberately broad so the vocabulary can capture mood identity
# without being too granular (granularity lives in expected_tags).
SEMANTIC_DIMENSIONS: frozenset[str] = frozenset({
    # ── Emotional state
    "sad", "happy", "angry", "euphoric", "peaceful", "anxious", "hollow",
    "lonely", "nostalgic", "melancholic", "cathartic", "tender", "confident",
    "emotional", "raw", "numb", "bittersweet", "hopeful", "aggressive",
    "celebratory", "meditative",

    # ── Energy / intensity
    "hype", "energy", "intense", "powerful", "heavy", "soft", "slow",
    "calm", "chaotic", "vibrant", "subtle", "explosive",

    # ── Context / setting
    "night", "morning", "summer", "dark", "warm", "cold", "atmospheric",
    "cinematic", "urban", "street", "freedom", "eerie", "mysterious",
    "liminal", "hazy", "ethereal", "minimal", "hypnotic",

    # ── Activity / mode
    "drive", "gym", "party", "focus", "sleep", "worship", "study",

    # ── Character / vibe
    "introspective", "romantic", "sexy", "groovy", "authentic", "soulful",
    "organic", "trippy", "rebellious", "menacing", "theatrical", "dramatic",
    "lush", "nautical", "marching", "anthemic", "sensual", "devotional",

    # ── Genre essence
    "acoustic", "electronic", "ambient", "phonk", "spiritual", "uplift",
    "love", "chill",
})


_PACKS: dict | None = None

# Shorter UI labels (internal pack keys stay stable for scoring / anchors / staging).
_DISPLAY_NAME_OVERRIDES: dict[str, str] = {
    "Late Night Drive": "Night Drive",
    "Smoke & Mirrors": "Smoke and Mirrors",
    "Golden Hour": "Golden Hour",
    "Weightless": "Sleepy",
    "Deep Focus": "Focus",
    "Euphoric Rave": "Rave",
    "Morning Ritual": "Morning",
    "Acoustic Corner": "Acoustic",
    "Midnight Clarity": "Late Night",
    "Phonk Season": "Phonk",
    "Raw Emotion": "Raw",
    "Open Road": "Road Trip",
    "Flex Tape": "Flex",
    "Dark Pop": "Dark Pop",
    "Emo Hour": "Emo",
    "Indie Bedroom": "Bedroom Indie",
    "Country Roads": "Country",
    "Gospel Fire": "Gospel",
    "Old School Hip-Hop": "Old School Rap",
    "K-Pop Zone": "K-Pop",
    "Sunday Reset": "Sunday Chill",
    "Synthwave Nights": "Synthwave",
    "Goth / Darkwave": "Goth",
    "Villain Arc": "Villain",
    "Healing Kind": "Self Care",
    "Rainy Window": "Rainy Day",
    "Meditation Bath": "Meditation",
    "Metal Storm": "Metal",
    "Rage Lift": "Gym Rage",
    "Disco Lights": "Disco",
    "Amapiano Sunset": "Amapiano",
    "Punk Sprint": "Punk",
    "Dream Pop Haze": "Dream Pop",
    "Warehouse Techno": "Techno",
    "Anime OST Energy": "Anime Mix",
    "Chillhop Cafe": "Chillhop",
    "Soft Hours": "Soft",
    "Liminal": "Weird Hours",
    "Hard Reset": "Reset",
    "Heartbreak": "Heartbreak",
    "Neo-Soul": "Neo Soul",
    "Psychedelic": "Psych Rock",
    "Slow Jams": "Slow Jams",
    "Jazz Nights": "Jazz Night",
}


def mood_display_name(mood_name: str) -> str:
    if mood_name in _DISPLAY_NAME_OVERRIDES:
        return _DISPLAY_NAME_OVERRIDES[mood_name]
    pack = get_mood(mood_name)
    if pack and pack.get("display_name"):
        return str(pack["display_name"])
    return mood_name


def mood_genre_neutral(mood_name: str) -> bool:
    pack = get_mood(mood_name)
    return bool(pack and pack.get("genre_neutral"))


def mood_lyric_focus(mood_name: str) -> bool:
    pack = get_mood(mood_name)
    return bool(pack and pack.get("lyric_focus"))


def mood_lyrical_expected_tags(mood_name: str) -> list[str]:
    pack = get_mood(mood_name)
    if not pack:
        return []
    raw = pack.get("lyrical_expected_tags") or []
    return [str(x) for x in raw]


def _load_packs() -> dict:
    global _PACKS
    if _PACKS is not None:
        return _PACKS
    path = os.path.join(os.path.dirname(__file__), "..", "data", "packs.json")
    with open(path, "r", encoding="utf-8") as f:
        _PACKS = json.load(f)["moods"]
    return _PACKS


def all_moods() -> dict:
    return _load_packs()


def get_mood(name: str) -> dict | None:
    packs = _load_packs()
    # Exact match first
    if name in packs:
        return packs[name]
    # Case-insensitive
    for k, v in packs.items():
        if k.lower() == name.lower():
            return v
    return None


def mood_audio_target(mood_name: str) -> list[float]:
    """Return the 6-dim audio vector target for a mood pack."""
    pack = get_mood(mood_name)
    if not pack:
        return [0.5] * 6
    t = pack.get("audio_target", {})
    return [
        t.get("energy",           0.5),
        t.get("valence",          0.5),
        t.get("danceability",     0.5),
        t.get("tempo_norm",       0.5),
        t.get("acousticness",     0.5),
        t.get("instrumentalness", 0.3),
    ]


def mood_expected_tags(mood_name: str) -> list[str]:
    pack = get_mood(mood_name)
    if not pack:
        return []
    return pack.get("expected_tags", [])


def mood_preferred_genres(mood_name: str) -> list[str]:
    pack = get_mood(mood_name)
    if not pack:
        return []
    return pack.get("preferred_macro_genres", [])


def _vec_dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _vec_mag(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity — used only for mood-to-mood comparisons (related_moods).
    Do NOT use for track-to-mood scoring; use gaussian_similarity instead."""
    mag_a, mag_b = _vec_mag(a), _vec_mag(b)
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return max(0.0, min(1.0, _vec_dot(a, b) / (mag_a * mag_b)))


def gaussian_similarity(a: list[float], b: list[float], sigma: float = 0.35) -> float:
    """
    Gaussian (RBF) similarity between two audio vectors.

    Returns exp(-||a-b||² / (2σ²)):
      • identical vectors  → 1.0
      • avg 0.1 diff/dim   → ~0.88  (very similar)
      • avg 0.2 diff/dim   → ~0.59  (similar)
      • avg 0.3 diff/dim   → ~0.27  (different)
      • avg 0.4 diff/dim   → ~0.08  (very different)

    Unlike cosine, this correctly penalises magnitude differences and does not
    treat [0.5]*6 as "close to everything".
    """
    if len(a) != len(b) or not a:
        return 0.0
    sq_dist = sum((x - y) ** 2 for x, y in zip(a, b))
    return math.exp(-sq_dist / (2.0 * sigma * sigma))


def mood_audio_constraints(mood_name: str) -> dict:
    """
    Return hard audio filter bounds for a mood.

    Keys present (all optional):
      energy_min, energy_max, valence_min, valence_max

    Only bounds that should be strictly enforced are included.
    Tracks that fail ANY present bound are rejected before scoring.
    Returns {} if the mood has no constraints or is unknown.
    """
    pack = get_mood(mood_name)
    if not pack:
        return {}
    return pack.get("audio_constraints", {})


def mood_forbidden_tags(mood_name: str) -> list[str]:
    """
    Return tags whose presence in a track's profile immediately disqualifies
    it from this mood.  An empty list means no tag-based rejection.
    """
    pack = get_mood(mood_name)
    if not pack:
        return []
    return pack.get("forbidden_tags", [])


def mood_forbidden_genres(mood_name: str) -> list[str]:
    """
    Return macro-genre names that disqualify a track from this mood.
    Matched against profile["macro_genres"].  Empty list = no rejection.
    """
    pack = get_mood(mood_name)
    if not pack:
        return []
    return pack.get("forbidden_genres", [])


def mood_semantic_core(mood_name: str) -> dict[str, float]:
    """
    Return the semantic dimension profile for a mood.

    Each mood in packs.json has a ``semantic_core`` key: a list of atomic
    emotional/contextual dimensions (from SEMANTIC_DIMENSIONS vocabulary)
    that define the mood's identity at the meaning layer — above raw tags,
    below audio features.

    If ``semantic_core`` is a list  → all dims get weight 1.0.
    If ``semantic_core`` is a dict  → weights used as-is.
    If ``semantic_core`` is absent  → returns {} (scorer falls back to 0.5).

    These dimensions form the input to scorer.semantic_score() and the
    semantic cohesion component of cohesion_filter().
    """
    pack = get_mood(mood_name)
    if not pack:
        return {}
    core = pack.get("semantic_core")
    if not core:
        return {}
    if isinstance(core, list):
        return {dim: 1.0 for dim in core}
    if isinstance(core, dict):
        return dict(core)
    return {}


def mood_semantic_similarity(mood_a: str, mood_b: str) -> float:
    """
    Jaccard similarity between two moods' semantic cores.

    Used by dedup_across_moods() to set dynamic win margins:
    moods that share many semantic dimensions require a larger score gap
    before a track is reassigned to just one of them.

    Returns 0.0 if either mood has no semantic core.
    """
    core_a = set(mood_semantic_core(mood_a).keys())
    core_b = set(mood_semantic_core(mood_b).keys())
    if not core_a or not core_b:
        return 0.0
    return len(core_a & core_b) / len(core_a | core_b)


def fuzzy_match(query: str, top_n: int = 3) -> list[tuple[str, float]]:
    """
    Match a freeform query string to the closest mood packs.
    Returns list of (mood_name, similarity_score) sorted by score desc.
    """
    packs = _load_packs()
    query_words = set(query.lower().split())
    scores: list[tuple[str, float]] = []

    for name, pack in packs.items():
        name_words = set(name.lower().split())
        seed_words: set[str] = set()
        for phrase in pack.get("seed_phrases", []):
            seed_words.update(phrase.lower().split())
        tag_words = set(pack.get("expected_tags", []))

        all_words = name_words | seed_words | tag_words
        if not all_words:
            continue

        overlap = len(query_words & all_words)
        score = overlap / math.sqrt(len(query_words) * len(all_words)) if overlap else 0.0
        scores.append((name, round(score, 4)))

    scores.sort(key=lambda x: -x[1])
    return scores[:top_n]


def related_moods(mood_name: str, top_n: int = 3) -> list[str]:
    """
    Find moods with similar audio targets (for 'you might also like' suggestions).
    """
    packs = _load_packs()
    target = mood_audio_target(mood_name)
    scores: list[tuple[str, float]] = []
    for name in packs:
        if name == mood_name:
            continue
        sim = cosine_similarity(target, mood_audio_target(name))
        scores.append((name, sim))
    scores.sort(key=lambda x: -x[1])
    return [name for name, _ in scores[:top_n]]
