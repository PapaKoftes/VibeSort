"""
cohesion.py — Measure and enforce playlist cohesion.

Cohesion = how similar the tracks in a playlist are to each other.
A score of 1.0 means every track is identical in audio character.
A score of 0.0 means the tracks are completely unrelated.

Good playlists: 0.75+ cohesion.
Acceptable: 0.60+.
Below 0.60: remove outliers until cohesion improves.
"""

import math
from core.mood_graph import cosine_similarity


def _centroid(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return [0.5] * 6
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(len(vectors[0]))]


def cohesion_score(uris: list[str], profiles: dict[str, dict]) -> float:
    """
    Average cosine similarity of all tracks to the group centroid.
    Returns 0.0 if not enough data.
    """
    vectors = [profiles[u]["audio_vector"] for u in uris if u in profiles]
    if len(vectors) < 2:
        return 1.0
    c = _centroid(vectors)
    sims = [cosine_similarity(v, c) for v in vectors]
    return round(sum(sims) / len(sims), 4)


def filter_outliers(
    uris: list[str],
    profiles: dict[str, dict],
    threshold: float = 0.60,
    min_tracks: int = 10,
) -> tuple[list[str], float]:
    """
    Remove tracks whose audio vector is too far from the group centroid.
    Keeps iterating until all remaining tracks meet the threshold or
    we'd drop below min_tracks.

    Returns (filtered_uris, final_cohesion_score).
    """
    current = [u for u in uris if u in profiles]
    if len(current) <= min_tracks:
        return current, cohesion_score(current, profiles)

    for _ in range(20):  # max 20 passes
        vectors = [profiles[u]["audio_vector"] for u in current]
        c = _centroid(vectors)
        sims = [(u, cosine_similarity(profiles[u]["audio_vector"], c)) for u in current]
        worst_sim = min(s for _, s in sims)

        if worst_sim >= threshold or len(current) <= min_tracks:
            break

        # Remove the single worst outlier per pass
        current = [u for u, s in sims if s > worst_sim or u == sims[0][0]]
        # Tie-break: keep all above worst, ensure we keep enough
        current = sorted(current, key=lambda u: -cosine_similarity(profiles[u]["audio_vector"], c))
        if len(current) > min_tracks:
            current = [u for u, s in sims if s >= threshold]
            if len(current) < min_tracks:
                # Fall back: just remove the single worst
                worst_uri = min(sims, key=lambda x: x[1])[0]
                current = [u for u in [x[0] for x in sims] if u != worst_uri]

    score = cohesion_score(current, profiles)
    return current, score


def top_n_by_score(
    scored: list[tuple[str, float]],
    profiles: dict[str, dict],
    n: int = 50,
    cohesion_threshold: float = 0.60,
    min_tracks: int = 10,
) -> tuple[list[str], float]:
    """
    Take top-N scored tracks, then apply cohesion filtering.
    Returns (track_uris, cohesion_score).
    """
    candidates = [uri for uri, _ in scored[:max(n * 2, 30)]]  # start wider
    filtered, score = filter_outliers(candidates, profiles, cohesion_threshold, min_tracks)
    return filtered[:n], score


def cohesion_label(score: float) -> str:
    if score >= 0.88:
        return "very cohesive"
    if score >= 0.78:
        return "cohesive"
    if score >= 0.65:
        return "decent"
    if score >= 0.50:
        return "loose"
    return "scattered"
