"""
blend.py — Multi-user Vibesort Blend.

Better than Spotify Blend because:
- Supports 3+ users
- Genre-aware (not just audio similarity)
- Generates multiple playlist angles per blend
"""

from __future__ import annotations

import time
from typing import Optional


def fetch_user_library(sp, playlist_urls: list[str]) -> dict[str, dict]:
    """
    Fetch all tracks from a list of Spotify playlist URLs and return them
    as a profile-keyed dict {uri: {"name": ..., "artists": [...], "uri": ...}}.

    This is used as a proxy for a user's library when they don't share their
    actual account.

    Args:
        sp:             Authenticated spotipy.Spotify instance.
        playlist_urls:  List of Spotify playlist URLs or URIs.

    Returns:
        Dict of {track_uri: track_dict} for all tracks found.
    """
    tracks: dict[str, dict] = {}
    for url in playlist_urls:
        if not url or not url.strip():
            continue
        playlist_id = _extract_playlist_id(url.strip())
        if not playlist_id:
            continue
        try:
            offset = 0
            while True:
                result = sp.playlist_tracks(
                    playlist_id,
                    offset=offset,
                    limit=100,
                    fields="items(track(uri,name,artists,popularity,album)),next",
                )
                items = result.get("items", [])
                for item in items:
                    track = item.get("track")
                    if not track or not track.get("uri"):
                        continue
                    uri = track["uri"]
                    tracks[uri] = {
                        "uri":        uri,
                        "name":       track.get("name", ""),
                        "artists":    [a["name"] for a in track.get("artists", [])],
                        "popularity": track.get("popularity", 50),
                    }
                if not result.get("next"):
                    break
                offset += 100
                time.sleep(0.05)
        except Exception:
            continue
    return tracks


def _extract_playlist_id(url: str) -> Optional[str]:
    """Extract playlist ID from a Spotify URL or URI."""
    # spotify:playlist:ID
    if url.startswith("spotify:playlist:"):
        return url.split(":")[2]
    # https://open.spotify.com/playlist/ID
    if "spotify.com/playlist/" in url:
        part = url.split("spotify.com/playlist/")[1]
        return part.split("?")[0].split("/")[0]
    # raw ID (22 chars)
    if len(url) == 22 and url.isalnum():
        return url
    return None


def compute_overlap(
    library_a: set[str],
    library_b: set[str],
) -> set[str]:
    """
    Return the intersection of two track URI sets.

    Args:
        library_a: Set of track URIs for user A.
        library_b: Set of track URIs for user B.

    Returns:
        Set of URIs present in both libraries.
    """
    return library_a & library_b


def compute_multi_overlap(libraries: list[set[str]]) -> set[str]:
    """
    Return URIs present in ALL provided libraries.

    Args:
        libraries: List of URI sets, one per user.

    Returns:
        Intersection of all sets.
    """
    if not libraries:
        return set()
    result = libraries[0].copy()
    for lib in libraries[1:]:
        result &= lib
    return result


def blend_profiles(
    profiles_a: dict[str, dict],
    profiles_b: dict[str, dict],
) -> dict[str, dict]:
    """
    Merge two profile dicts into one combined dict.
    Tracks present in both libraries are included once (profiles_a takes precedence).

    Args:
        profiles_a: Track profiles for user A.
        profiles_b: Track profiles for user B.

    Returns:
        Combined dict of all profiles.
    """
    merged = dict(profiles_b)
    merged.update(profiles_a)
    return merged


def _audio_mean(uris: list[str], profiles: dict[str, dict]) -> list[float]:
    """Compute mean audio vector for a list of URIs."""
    vectors = [
        profiles[u]["audio_vector"]
        for u in uris
        if u in profiles and profiles[u].get("audio_vector")
    ]
    if not vectors:
        return [0.5] * 6
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(6)]


def _genre_breakdown(uris: list[str], profiles: dict[str, dict]) -> dict[str, int]:
    """Count macro genres for a list of URIs."""
    counts: dict[str, int] = {}
    for uri in uris:
        p = profiles.get(uri, {})
        for macro in p.get("macro_genres", ["Other"]):
            counts[macro] = counts.get(macro, 0) + 1
    return counts


def _cohesion_score(uris: list[str], profiles: dict[str, dict]) -> float:
    """Compute a simple cohesion score for a set of URIs."""
    if len(uris) < 2:
        return 1.0
    try:
        import numpy as np
        vectors = np.array([
            profiles[u]["audio_vector"]
            for u in uris
            if u in profiles and profiles[u].get("audio_vector")
        ])
        if len(vectors) < 2:
            return 1.0
        mean = vectors.mean(axis=0)
        dists = np.linalg.norm(vectors - mean, axis=1)
        avg_dist = float(dists.mean())
        score = max(0.0, 1.0 - avg_dist)
        return round(score, 3)
    except Exception:
        return 0.7


def generate_blend_playlists(
    sp,
    user_profiles: list[tuple[str, dict[str, dict]]],
    profiles_combined: dict[str, dict],
    cfg,
) -> list[dict]:
    """
    Generate blend playlist data dicts from multiple users' profiles.

    Generates three playlist angles:
    1. "Common Ground" — tracks that appear in all users' libraries
    2. "The Meeting Point" — scored blend using averaged audio means
    3. "Genre Overlap" — genres shared by all users

    Args:
        sp:                Authenticated spotipy.Spotify instance.
        user_profiles:     List of (username, {uri: profile}) tuples.
        profiles_combined: Merged profiles dict.
        cfg:               Config module with MAX_TRACKS_PER_PLAYLIST etc.

    Returns:
        List of playlist data dicts (not yet staged). Each dict is ready
        to be passed to staging.staging.save().
    """
    if len(user_profiles) < 2:
        return []

    libraries = [set(profiles.keys()) for _, profiles in user_profiles]
    max_tracks = getattr(cfg, "MAX_TRACKS_PER_PLAYLIST", 50)

    results = []

    # ── Playlist 1: Common Ground ─────────────────────────────────────────────
    common_uris = list(compute_multi_overlap(libraries))
    if common_uris:
        common_uris = common_uris[:max_tracks]
        audio = _audio_mean(common_uris, profiles_combined)
        genre_bd = _genre_breakdown(common_uris, profiles_combined)
        cohesion = _cohesion_score(common_uris, profiles_combined)
        top_genre = max(genre_bd.items(), key=lambda x: x[1], default=("Mixed", 0))[0]
        results.append({
            "suggested_name": "Common Ground",
            "user_name":      "Common Ground",
            "description":    (
                f"Songs you all have in common. {len(common_uris)} shared tracks. "
                f"Top genre: {top_genre}."
            ),
            "track_uris":     common_uris,
            "rec_uris":       [],
            "playlist_type":  "blend",
            "genre_breakdown": genre_bd,
            "cohesion":       cohesion,
            "expand_with_recs": False,
            "metadata": {
                "blend_angle": "common_ground",
                "user_count":  len(user_profiles),
            },
        })

    # ── Playlist 2: The Meeting Point ─────────────────────────────────────────
    # All tracks that appear in at least 2 users' libraries, scored by audio similarity
    at_least_two: list[str] = []
    if len(libraries) >= 2:
        union = libraries[0].copy()
        for lib in libraries[1:]:
            union |= lib
        for uri in union:
            count = sum(1 for lib in libraries if uri in lib)
            if count >= 2:
                at_least_two.append(uri)

    if at_least_two:
        # Score by distance to the average audio mean across all users
        user_means = []
        for _, profs in user_profiles:
            uris = list(profs.keys())
            user_means.append(_audio_mean(uris, profs))
        if user_means:
            n = len(user_means)
            global_mean = [sum(m[i] for m in user_means) / n for i in range(6)]

            def dist_to_mean(uri: str) -> float:
                vec = profiles_combined.get(uri, {}).get("audio_vector")
                if not vec:
                    return 999.0
                return sum((v - g) ** 2 for v, g in zip(vec, global_mean)) ** 0.5

            at_least_two.sort(key=dist_to_mean)
            meeting_uris = at_least_two[:max_tracks]
        else:
            meeting_uris = at_least_two[:max_tracks]

        audio = _audio_mean(meeting_uris, profiles_combined)
        genre_bd = _genre_breakdown(meeting_uris, profiles_combined)
        cohesion = _cohesion_score(meeting_uris, profiles_combined)
        top_genre = max(genre_bd.items(), key=lambda x: x[1], default=("Mixed", 0))[0]
        results.append({
            "suggested_name": "The Meeting Point",
            "user_name":      "The Meeting Point",
            "description":    (
                f"A blend of your shared musical DNA. {len(meeting_uris)} tracks, "
                f"centred around {top_genre}."
            ),
            "track_uris":     meeting_uris,
            "rec_uris":       [],
            "playlist_type":  "blend",
            "genre_breakdown": genre_bd,
            "cohesion":       cohesion,
            "expand_with_recs": True,
            "metadata": {
                "blend_angle": "meeting_point",
                "user_count":  len(user_profiles),
            },
        })

    # ── Playlist 3: Genre Overlap ─────────────────────────────────────────────
    # Find the macro genre that all users have the most tracks in, make a playlist
    user_genre_sets: list[dict[str, int]] = []
    for _, profs in user_profiles:
        gbd = _genre_breakdown(list(profs.keys()), profs)
        user_genre_sets.append(gbd)

    # Genres present in all users
    shared_genres: set[str] = set(user_genre_sets[0].keys())
    for gbd in user_genre_sets[1:]:
        shared_genres &= set(gbd.keys())
    shared_genres.discard("Other")

    if shared_genres:
        # Pick the genre with highest combined count
        best_genre = max(
            shared_genres,
            key=lambda g: sum(gbd.get(g, 0) for gbd in user_genre_sets),
        )
        # Collect tracks from that genre from all users
        genre_uris: list[str] = []
        for _, profs in user_profiles:
            for uri, profile in profs.items():
                if best_genre in profile.get("macro_genres", []):
                    genre_uris.append(uri)
        # Deduplicate and cap
        genre_uris = list(dict.fromkeys(genre_uris))[:max_tracks]

        if genre_uris:
            genre_bd = _genre_breakdown(genre_uris, profiles_combined)
            cohesion = _cohesion_score(genre_uris, profiles_combined)
            results.append({
                "suggested_name": f"Shared {best_genre}",
                "user_name":      f"Shared {best_genre}",
                "description":    (
                    f"Your shared love of {best_genre}. "
                    f"{len(genre_uris)} tracks from all users."
                ),
                "track_uris":     genre_uris,
                "rec_uris":       [],
                "playlist_type":  "blend",
                "genre_breakdown": genre_bd,
                "cohesion":       cohesion,
                "expand_with_recs": True,
                "metadata": {
                    "blend_angle":  "genre_overlap",
                    "shared_genre": best_genre,
                    "user_count":   len(user_profiles),
                },
            })

    return results
