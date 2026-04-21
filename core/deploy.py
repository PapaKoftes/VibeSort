"""
deploy.py — Batch deploy staged playlists to Spotify.

Reads from the staging shelf and pushes each playlist to the user's
Spotify account. Handles recommendations fetching, naming, and marking
deployed records.
"""

import time
from typing import Optional

import spotipy

import config
from core.spotify_retry import call_with_429_backoff
from staging import staging


def deploy_one(
    sp: spotipy.Spotify,
    user_id: str,
    staged: dict,
    profiles: dict | None = None,
    existing_uris: set | None = None,
) -> str:
    """
    Deploy a single staged playlist to Spotify.

    Uses user_name if set, else falls back to suggested_name.
    Prepends the configured PLAYLIST_PREFIX (default "Vibesort: ").
    Adds rec_uris to the playlist if expand_with_recs is True and rec_uris is populated.
    Marks the playlist as deployed in the staging shelf.

    Args:
        sp:       Authenticated Spotipy client.
        user_id:  Spotify user ID.
        staged:   Staged playlist dict from the staging shelf.

    Returns:
        The Spotify playlist URL.

    Raises:
        spotipy.SpotifyException: On API errors.
    """
    display_name = staging.get_display_name(staged)
    prefix = config.PLAYLIST_PREFIX
    full_name = f"{prefix}{display_name}" if prefix else display_name

    track_uris  = list(staged.get("track_uris", []))
    rec_uris    = list(staged.get("rec_uris", []))
    expand      = staged.get("expand_with_recs", False)
    description = staged.get("description", f"{len(track_uris)} tracks. Made by Vibesort.")
    cohesion    = staged.get("cohesion", 0.0)

    # If expand is on but recs were never fetched, fetch them now
    if expand and not rec_uris and profiles is not None and existing_uris is not None:
        try:
            _min_total = int(getattr(config, "MIN_PLAYLIST_TOTAL", 30))
            _short = max(0, _min_total - len(track_uris))
            _n = max(int(getattr(config, "RECS_PER_PLAYLIST", 22)), _short + 10, 15)
            rec_uris = fetch_recs_for_staged(
                sp, staged, profiles, existing_uris,
                n=min(_n, 100),
            )
        except Exception:
            rec_uris = []

    if cohesion:
        cohesion_note = f" {round(cohesion * 100)}% cohesive."
        if "cohesive" not in description:
            description = description.rstrip(".") + "." + cohesion_note

    # Build final track list
    if expand and rec_uris:
        all_uris = list(dict.fromkeys(track_uris + rec_uris))
    else:
        all_uris = list(dict.fromkeys(track_uris))

    max_tracks = int(getattr(config, "MAX_TRACKS_PER_PLAYLIST", 75))
    all_uris = all_uris[:max_tracks]

    # Create the Spotify playlist (retry on 429 — burst deploys can rate-limit)
    playlist = call_with_429_backoff(
        lambda: sp.user_playlist_create(
            user=user_id,
            name=full_name,
            public=False,
            description=description,
        )
    )
    pid = playlist["id"]
    url = playlist["external_urls"]["spotify"]

    # Add tracks in batches of 100 (Spotify limit)
    for i in range(0, len(all_uris), 100):
        batch = all_uris[i : i + 100]
        call_with_429_backoff(lambda b=batch: sp.playlist_add_items(pid, b))
        time.sleep(0.08)

    # Mark as deployed
    staging.mark_deployed(staged["id"], url)

    return url


def deploy_all(
    sp: spotipy.Spotify,
    user_id: str,
    staged_list: list[dict],
    profiles: dict | None = None,
    existing_uris: set | None = None,
) -> list[dict]:
    """
    Deploy all staged playlists in the provided list.

    Processes them in order, handling errors per-playlist so one failure
    does not abort the rest.

    Args:
        sp:           Authenticated Spotipy client.
        user_id:      Spotify user ID.
        staged_list:  List of staged playlist dicts.

    Returns:
        List of result dicts:
        [{"name": str, "url": str | None, "success": bool, "error": str | None}, ...]
    """
    results = []
    for staged in staged_list:
        name = staging.get_display_name(staged)
        try:
            url = deploy_one(sp, user_id, staged, profiles=profiles, existing_uris=existing_uris)
            results.append({
                "name":    name,
                "url":     url,
                "success": True,
                "error":   None,
            })
        except spotipy.SpotifyException as exc:
            results.append({
                "name":    name,
                "url":     None,
                "success": False,
                "error":   f"Spotify API error: {exc.http_status} — {exc.msg}",
            })
        except Exception as exc:  # noqa: BLE001
            results.append({
                "name":    name,
                "url":     None,
                "success": False,
                "error":   str(exc),
            })
        # Small delay between deploys to avoid rate limits
        time.sleep(0.3)

    return results


def fetch_recs_for_staged(
    sp: spotipy.Spotify,
    staged: dict,
    profiles: dict,
    existing_uris: set,
    n: int = 15,
) -> list[str]:
    """
    Fetch recommendations for a staged playlist and store them in staging.

    Uses Last.fm track.getSimilar + Spotify search as the recommendation
    source (Spotify's /v1/recommendations was deprecated November 2024).

    Uses the playlist's track_uris as seeds and the source_type/source_label
    to determine the mood context (if applicable).

    Args:
        sp:            Authenticated Spotipy client.
        staged:        Staged playlist dict.
        profiles:      Full track profiles dict {uri: profile}.
        existing_uris: Set of URIs already in the user's library.
        n:             Number of recommendations to fetch.

    Returns:
        List of recommended track URIs (not in existing library).
    """
    from core.recommend import filtered_recommendations

    track_uris   = staged.get("track_uris", [])
    source_type  = staged.get("source_type", "genre")
    source_label = staged.get("source_label", "")

    if not track_uris:
        return []

    # Resolve Last.fm API key from config (shared Vibesort key or per-user key)
    lastfm_api_key = (
        getattr(config, "VIBESORT_LASTFM_API_KEY", "").strip()
        or getattr(config, "LASTFM_API_KEY", "").strip()
    )

    # Mood name is only relevant for mood-type playlists
    mood_name: Optional[str] = source_label if source_type == "mood" else None

    rec_uris, _fallback = filtered_recommendations(
        sp=sp,
        seed_uris=track_uris,
        profiles=profiles,
        existing_uris=existing_uris,
        mood_name=mood_name or "",
        n=n,
        cohesion_threshold=config.COHESION_THRESHOLD,
        lastfm_api_key=lastfm_api_key,
    )

    # Persist the recs into the staged record
    staging.update(staged["id"], {"rec_uris": rec_uris})
    return rec_uris
