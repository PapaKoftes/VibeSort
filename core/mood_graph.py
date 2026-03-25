"""
mood_graph.py — Load mood pack definitions and provide fuzzy matching.

The mood graph connects moods to each other so that:
  - "late night drive" relates to "overthinking" and "hollow"
  - "overflow" relates to "pre-game" and "adrenaline"

This enables fuzzy vibe matching: user types "something dark and floaty"
and we can find the closest packs.
"""

import json
import os
import math


_PACKS: dict | None = None


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
    mag_a, mag_b = _vec_mag(a), _vec_mag(b)
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return max(0.0, min(1.0, _vec_dot(a, b) / (mag_a * mag_b)))


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
