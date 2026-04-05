"""
builder.py — Create Spotify playlists from scored track lists.
"""

import time
import spotipy

from core.spotify_retry import call_with_429_backoff


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
    desc = description or f"{len(track_uris)} tracks. Made by Vibesort."
    playlist = call_with_429_backoff(
        lambda: sp.user_playlist_create(
            user=user_id,
            name=name,
            public=public,
            description=desc,
        )
    )
    pid = playlist["id"]

    all_uris = list(dict.fromkeys(track_uris + (rec_uris or [])))
    for i in range(0, len(all_uris), 100):
        batch = all_uris[i : i + 100]
        call_with_429_backoff(lambda b=batch: sp.playlist_add_items(pid, b))
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
    profiles: dict | None = None,
    top_tags: list[str] | None = None,
) -> str:
    """
    Create a mood playlist. When ``profiles`` is set, uses the same top-down naming
    and lyric-aware descriptions as the Streamlit Vibes flow.
    """
    from core.mood_graph import get_mood, mood_display_name

    pack = get_mood(mood_name) or {}
    rec_note = f" + {len(rec_uris)} similar songs" if rec_uris else ""
    cohesion_note = f"{round(cohesion * 100)}% cohesive."

    track_profiles: list[dict] = []
    if profiles and track_uris:
        track_profiles = [profiles[u] for u in track_uris if u in profiles]

    if track_profiles:
        try:
            from core.namer import top_down_name

            obs: dict[str, float] = {}
            if top_tags:
                obs = {
                    t: float(max(1.0 - (i * 0.08), 0.3))
                    for i, t in enumerate(top_tags[:8])
                }
            display_name, description = top_down_name(
                mood_name,
                track_profiles,
                observed_tags=obs or None,
            )
            if rec_uris and "similar" not in description.lower():
                description = description.rstrip()
                if not description.endswith("."):
                    description += "."
                description += f" + {len(rec_uris)} similar songs."
            if "cohesive" not in description.lower():
                description = description.rstrip()
                if not description.endswith("."):
                    description += "."
                description += f" {cohesion_note}"
            if "vibesort" not in description.lower():
                description = description.rstrip()
                if not description.endswith("."):
                    description += "."
                description += " Made by Vibesort."
        except Exception:
            desc_text = pack.get("description", mood_name)
            description = (
                f"{desc_text}. {len(track_uris)} tracks{rec_note}. "
                f"{cohesion_note} Made by Vibesort."
            )
            display_name = mood_display_name(mood_name)
    else:
        desc_text = pack.get("description", mood_name)
        description = (
            f"{desc_text}. {len(track_uris)} tracks{rec_note}. "
            f"{cohesion_note} Made by Vibesort."
        )
        display_name = mood_display_name(mood_name)

    name = f"{prefix}{display_name}" if prefix else display_name
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
