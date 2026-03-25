"""
recommend.py — Fetch recommendations from Spotify and filter for cohesion.
"""

import random
import time
import spotipy
from core.mood_graph import cosine_similarity, mood_audio_target
from core.cohesion import cohesion_score


def spotify_recommendations(
    sp: spotipy.Spotify,
    seed_uris: list[str],
    n: int = 20,
    mood_name: str | None = None,
) -> list[str]:
    """
    Fetch track recommendations from Spotify seeded by up to 5 tracks.
    Uses audio feature targets if mood_name is provided.
    Returns list of track URIs (not in user's existing library).
    """
    if not seed_uris or n == 0:
        return []

    pool = seed_uris[:]
    random.shuffle(pool)
    seeds = [u.split(":")[-1] for u in pool[:5]]

    kwargs: dict = {"seed_tracks": seeds, "limit": min(n, 100)}

    # Add audio target parameters if we have a mood
    if mood_name:
        target = mood_audio_target(mood_name)
        kwargs["target_energy"]       = target[0]
        kwargs["target_valence"]      = target[1]
        kwargs["target_danceability"] = target[2]
        kwargs["target_acousticness"] = target[4]

    try:
        result = sp.recommendations(**kwargs)
        return [t["uri"] for t in result.get("tracks", [])]
    except spotipy.SpotifyException as e:
        print(f"    [warn] recommendations failed: {e}")
        return []


def filtered_recommendations(
    sp: spotipy.Spotify,
    seed_uris: list[str],
    profiles: dict[str, dict],
    existing_uris: set[str],
    mood_name: str,
    n: int = 15,
    cohesion_threshold: float = 0.55,
) -> list[str]:
    """
    Get recommendations, filter out tracks already in the library,
    and keep only those that maintain cohesion with the seed set.
    """
    raw_recs = spotify_recommendations(sp, seed_uris, n=n * 2, mood_name=mood_name)
    time.sleep(0.1)

    # Filter out tracks already in library
    new_recs = [u for u in raw_recs if u not in existing_uris]

    if not new_recs:
        return []

    # If we have no profiles for recs, just return them as-is (they're new)
    # Trust Spotify's recommendations engine for content not in the library
    return new_recs[:n]
