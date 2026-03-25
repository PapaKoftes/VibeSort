"""
enrich.py — Add audio features and artist genre data to tracks.
"""

import time
import spotipy


def artist_genres(sp: spotipy.Spotify, artist_ids: list[str]) -> dict[str, list[str]]:
    """Returns {artist_id: [genre, ...]} for all given IDs (batched)."""
    result: dict[str, list[str]] = {}
    ids = list(set(artist_ids))
    for i in range(0, len(ids), 50):
        batch = sp.artists(ids[i:i+50])
        for a in batch.get("artists", []):
            if a:
                result[a["id"]] = a.get("genres", [])
        time.sleep(0.08)
    return result


def audio_features(sp: spotipy.Spotify, track_uris: list[str]) -> dict[str, dict]:
    """Returns {uri: feature_dict} for all given track URIs (batched)."""
    features: dict[str, dict] = {}
    ids = [u.split(":")[-1] for u in track_uris if u.startswith("spotify:track:")]
    for i in range(0, len(ids), 100):
        batch = sp.audio_features(ids[i:i+100]) or []
        for f in batch:
            if f:
                features[f"spotify:track:{f['id']}"] = f
        time.sleep(0.08)
    return features


def gather(sp: spotipy.Spotify, tracks: list[dict]) -> tuple[dict[str, list[str]], dict[str, dict]]:
    """
    Convenience: fetch both artist genres and audio features for a track list.
    Returns (artist_genres_map, audio_features_map).
    """
    artist_ids = [a["id"] for t in tracks for a in t.get("artists", [])]
    print(f"  Fetching genre data   ({len(set(artist_ids))} artists)...", end="", flush=True)
    genres = artist_genres(sp, artist_ids)
    print(f"\r  Genre data            done ({len(genres)} artists)")

    uris = [t["uri"] for t in tracks if t.get("uri")]
    print(f"  Fetching audio features ({len(uris)} tracks)...", end="", flush=True)
    features = audio_features(sp, uris)
    print(f"\r  Audio features        done ({len(features)} tracks)")

    return genres, features
