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

import math
from core.mood_graph import cosine_similarity, mood_audio_target, mood_expected_tags, mood_preferred_genres


# Default scoring weights (sum to 1.0, pref is a multiplier not additive)
W_AUDIO = 0.45
W_TAGS  = 0.35
W_GENRE = 0.20


# ── Individual signal scores ──────────────────────────────────────────────────

def audio_score(profile: dict, target_vector: list[float]) -> float:
    """Cosine similarity between track's audio vector and mood's audio target."""
    return cosine_similarity(profile["audio_vector"], target_vector)


def tag_score(profile: dict, expected_tags: list[str]) -> float:
    """
    Weighted overlap between track's mined tags and mood's expected tags.
    Score is in [0, 1]: how much of the expected tag set the track matches.
    """
    if not expected_tags or not profile["tags"]:
        return 0.0
    total = 0.0
    for tag in expected_tags:
        # Exact match
        if tag in profile["tags"]:
            total += profile["tags"][tag]
            continue
        # Partial match (tag is a substring of a mined compound tag)
        for mined_tag, weight in profile["tags"].items():
            if tag in mined_tag or mined_tag in tag:
                total += weight * 0.6
                break
    return min(total / len(expected_tags), 1.0)


def genre_score(profile: dict, preferred_genres: list[str]) -> float:
    """
    Binary overlap: does any of the track's macro genres match the mood's preferred genres?
    Returns 1.0 for match, 0.5 for partial (Other), 0.0 for no match.
    """
    if not preferred_genres:
        return 0.5
    if not profile["macro_genres"]:
        return 0.0
    for macro in profile["macro_genres"]:
        if macro in preferred_genres:
            return 1.0
    if "Other" in profile["macro_genres"]:
        return 0.3
    return 0.0


def user_preference_boost(profile: dict, user_audio_mean: list[float]) -> float:
    """
    Boost tracks that are close to the user's overall library taste.
    Returns a multiplier between 0.85 and 1.15.
    """
    sim = cosine_similarity(profile["audio_vector"], user_audio_mean)
    # Map [0,1] similarity to [0.85, 1.15] boost
    return 0.85 + (sim * 0.30)


# ── Combined score ─────────────────────────────────────────────────────────────

def score_track(
    profile: dict,
    mood_name: str,
    user_audio_mean: list[float] | None = None,
    weights: tuple[float, float, float] = (W_AUDIO, W_TAGS, W_GENRE),
) -> float:
    """
    Compute the full multi-signal score for a track against a mood.
    Returns a float in roughly [0, 1].
    """
    w_audio, w_tags, w_genre = weights
    target_vec = mood_audio_target(mood_name)
    exp_tags   = mood_expected_tags(mood_name)
    pref_genres = mood_preferred_genres(mood_name)

    a = audio_score(profile, target_vec)
    t = tag_score(profile, exp_tags)
    g = genre_score(profile, pref_genres)

    base = w_audio * a + w_tags * t + w_genre * g

    if user_audio_mean:
        base *= user_preference_boost(profile, user_audio_mean)

    return round(base, 6)


def rank_tracks(
    profiles: dict[str, dict],
    mood_name: str,
    user_audio_mean: list[float] | None = None,
    min_score: float = 0.25,
    weights: tuple[float, float, float] = (W_AUDIO, W_TAGS, W_GENRE),
) -> list[tuple[str, float]]:
    """
    Score all tracks in the profile dict for a given mood.
    Returns [(uri, score), ...] sorted by score descending.
    Only includes tracks with score >= min_score.
    """
    scored = []
    for uri, profile in profiles.items():
        s = score_track(profile, mood_name, user_audio_mean, weights)
        if s >= min_score:
            scored.append((uri, s))
    scored.sort(key=lambda x: -x[1])
    return scored


def explain(profile: dict, mood_name: str) -> list[str]:
    """
    Generate human-readable explanation bullets for why a track
    was included in a mood playlist.
    """
    reasons = []
    target_vec = mood_audio_target(mood_name)
    exp_tags   = mood_expected_tags(mood_name)
    pref_genres = mood_preferred_genres(mood_name)

    a_score = audio_score(profile, target_vec)
    t_score = tag_score(profile, exp_tags)
    g_score = genre_score(profile, pref_genres)

    if a_score > 0.7:
        reasons.append(f"audio profile matches ({a_score:.0%})")
    if t_score > 0.3 and profile["tags"]:
        top_tags = sorted(profile["tags"].items(), key=lambda x: -x[1])[:3]
        reasons.append("appears in playlists: " + ", ".join(t for t, _ in top_tags))
    if g_score > 0.5 and profile["macro_genres"]:
        reasons.append("genre: " + ", ".join(profile["macro_genres"][:2]))

    return reasons or ["audio feature match"]
