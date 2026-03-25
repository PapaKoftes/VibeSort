"""
builder.py — Create Spotify playlists from scored track lists.
"""

import time
import spotipy


def create(
    sp: spotipy.Spotify,
    user_id: str,
    name: str,
    track_uris: list[str],
    rec_uris: list[str] | None = None,
    description: str = "",
    public: bool = False,
) -> str:
    """
    Create a Spotify playlist, add library tracks, then recommendations.
    Returns the playlist URL.
    """
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=public,
        description=description or f"{len(track_uris)} tracks. Made by Vibesort.",
    )
    pid = playlist["id"]

    all_uris = list(dict.fromkeys(track_uris + (rec_uris or [])))
    for i in range(0, len(all_uris), 100):
        sp.playlist_add_items(pid, all_uris[i:i+100])
        time.sleep(0.08)

    return playlist["external_urls"]["spotify"]


def build_mood_playlist(
    sp: spotipy.Spotify,
    user_id: str,
    mood_name: str,
    track_uris: list[str],
    cohesion: float,
    rec_uris: list[str] | None = None,
    prefix: str = "",
) -> str:
    from core.mood_graph import get_mood
    pack = get_mood(mood_name) or {}
    desc_text = pack.get("description", mood_name)
    rec_note = f" + {len(rec_uris)} similar songs" if rec_uris else ""
    description = (
        f"{desc_text}. "
        f"{len(track_uris)} tracks{rec_note}. "
        f"{round(cohesion * 100)}% cohesive. Made by Vibesort."
    )
    name = f"{prefix}{mood_name}" if prefix else mood_name
    return create(sp, user_id, name, track_uris, rec_uris, description)


def build_genre_playlist(
    sp: spotipy.Spotify,
    user_id: str,
    genre_name: str,
    track_uris: list[str],
    rec_uris: list[str] | None = None,
    prefix: str = "",
) -> str:
    rec_note = f" + {len(rec_uris)} similar songs" if rec_uris else ""
    description = (
        f"Genre: {genre_name}. "
        f"{len(track_uris)} tracks{rec_note}. Made by Vibesort."
    )
    name = f"{prefix}{genre_name}" if prefix else genre_name
    return create(sp, user_id, name, track_uris, rec_uris, description)


def build_generic_playlist(
    sp: spotipy.Spotify,
    user_id: str,
    label: str,
    track_uris: list[str],
    rec_uris: list[str] | None = None,
    description: str = "",
    prefix: str = "",
) -> str:
    name = f"{prefix}{label}" if prefix else label
    return create(sp, user_id, name, track_uris, rec_uris, description)
