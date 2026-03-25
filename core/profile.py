"""
profile.py — Build unified track profiles combining all signal layers.

A track profile unifies:
  Layer 1: audio_vector    (Spotify audio features, normalized)
  Layer 2: genres          (raw Spotify genres from artist)
  Layer 3: macro_genres    (mapped to ~15 broad categories)
  Layer 4: tags            (from playlist mining, weighted)
  Layer 5: popularity      (Spotify popularity score 0-100)

The audio vector is: [energy, valence, danceability, tempo_norm,
                      acousticness, instrumentalness]
Tempo is normalized by dividing by 200 (covers ~60-200 BPM range).
"""

from core.genre import to_macro

AUDIO_KEYS = ["energy", "valence", "danceability", "acousticness", "instrumentalness"]


def _audio_vector(features: dict) -> list[float]:
    """Normalized 6-dim audio vector."""
    if not features:
        return [0.5] * 6
    tempo_norm = min(features.get("tempo", 120) / 200.0, 1.0)
    return [
        features.get("energy",           0.5),
        features.get("valence",          0.5),
        features.get("danceability",     0.5),
        tempo_norm,
        features.get("acousticness",     0.5),
        features.get("instrumentalness", 0.0),
    ]


def build(
    track: dict,
    artist_genres_map: dict[str, list[str]],
    audio_features_map: dict[str, dict],
    track_tags: dict[str, dict[str, float]],
) -> dict:
    """
    Build a full profile for one track.

    Returns:
      {
        uri, name, artists,
        audio_vector,
        raw_genres, macro_genres,
        tags,
        popularity,
      }
    """
    uri = track.get("uri", "")
    features = audio_features_map.get(uri, {})

    raw_genres: list[str] = []
    macro_seen: set[str] = set()
    macro_genres: list[str] = []
    for artist in track.get("artists", []):
        for genre in artist_genres_map.get(artist["id"], []):
            if genre not in raw_genres:
                raw_genres.append(genre)
            macro = to_macro(genre)
            if macro not in macro_seen:
                macro_seen.add(macro)
                macro_genres.append(macro)

    return {
        "uri":          uri,
        "name":         track.get("name", ""),
        "artists":      [a.get("name", "") for a in track.get("artists", [])],
        "audio_vector": _audio_vector(features),
        "raw_genres":   raw_genres,
        "macro_genres": macro_genres or ["Other"],
        "tags":         track_tags.get(uri, {}),
        "popularity":   track.get("popularity", 50),
        "_features":    features,   # kept for scorer access
    }


def build_all(
    tracks: list[dict],
    artist_genres_map: dict[str, list[str]],
    audio_features_map: dict[str, dict],
    track_tags: dict[str, dict[str, float]],
) -> dict[str, dict]:
    """Build profiles for all tracks. Returns {uri: profile}."""
    profiles: dict[str, dict] = {}
    for track in tracks:
        uri = track.get("uri")
        if uri:
            profiles[uri] = build(track, artist_genres_map, audio_features_map, track_tags)
    return profiles


def user_audio_mean(profiles: dict[str, dict]) -> list[float]:
    """Compute the mean audio vector across the entire library (user taste centroid)."""
    vectors = [p["audio_vector"] for p in profiles.values()]
    if not vectors:
        return [0.5] * 6
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(6)]


def user_tag_preferences(profiles: dict[str, dict]) -> dict[str, float]:
    """Aggregate tag weights across the library to understand preferred vibes."""
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for p in profiles.values():
        for tag, w in p["tags"].items():
            totals[tag] = totals.get(tag, 0) + w
            counts[tag] = counts.get(tag, 0) + 1
    # Return average weight per tag
    return {tag: totals[tag] / counts[tag] for tag in totals}
