"""
lastfm.py — Last.fm integration for Vibesort.

Provides listening history enrichment via the Last.fm API.
All functions handle errors gracefully and return empty results on failure.
pylast is optional — functions return None/empty if not installed.
"""

from __future__ import annotations

from typing import Optional


def connect(
    api_key: str,
    api_secret: str,
    username: str,
) -> Optional[object]:
    """
    Create and return a pylast.LastFMNetwork instance.

    Args:
        api_key:    Last.fm API key.
        api_secret: Last.fm API secret.
        username:   Last.fm username.

    Returns:
        pylast.LastFMNetwork instance, or None if pylast is not installed
        or credentials are missing.
    """
    if not api_key or not api_secret:
        return None
    try:
        import pylast
        network = pylast.LastFMNetwork(
            api_key=api_key,
            api_secret=api_secret,
            username=username,
        )
        return network
    except ImportError:
        return None
    except Exception:
        return None


def top_tracks(
    network,
    username: str,
    period: str = "PERIOD_OVERALL",
    limit: int = 200,
) -> list[dict]:
    """
    Fetch a user's top tracks from Last.fm.

    Args:
        network:  pylast.LastFMNetwork instance.
        username: Last.fm username.
        period:   One of PERIOD_OVERALL, PERIOD_7DAYS, PERIOD_1MONTH,
                  PERIOD_3MONTHS, PERIOD_6MONTHS, PERIOD_12MONTHS.
        limit:    Maximum number of tracks to return.

    Returns:
        List of dicts: [{title, artist, playcount}, ...]
    """
    if network is None:
        return []
    try:
        import pylast
        period_map = {
            "PERIOD_OVERALL":  pylast.PERIOD_OVERALL,
            "PERIOD_7DAYS":    pylast.PERIOD_7DAYS,
            "PERIOD_1MONTH":   pylast.PERIOD_1MONTH,
            "PERIOD_3MONTHS":  pylast.PERIOD_3MONTHS,
            "PERIOD_6MONTHS":  pylast.PERIOD_6MONTHS,
            "PERIOD_12MONTHS": pylast.PERIOD_12MONTHS,
        }
        resolved_period = period_map.get(period, pylast.PERIOD_OVERALL)
        user = network.get_user(username)
        items = user.get_top_tracks(period=resolved_period, limit=limit)
        results = []
        for item in items:
            try:
                results.append({
                    "title":     item.item.get_name(),
                    "artist":    item.item.get_artist().get_name(),
                    "playcount": int(item.weight),
                })
            except Exception:
                continue
        return results
    except Exception:
        return []


def top_artists(
    network,
    username: str,
    period: str = "PERIOD_OVERALL",
    limit: int = 50,
) -> list[dict]:
    """
    Fetch a user's top artists from Last.fm.

    Args:
        network:  pylast.LastFMNetwork instance.
        username: Last.fm username.
        period:   Time period string (see top_tracks for options).
        limit:    Maximum number of artists to return.

    Returns:
        List of dicts: [{name, playcount}, ...]
    """
    if network is None:
        return []
    try:
        import pylast
        period_map = {
            "PERIOD_OVERALL":  pylast.PERIOD_OVERALL,
            "PERIOD_7DAYS":    pylast.PERIOD_7DAYS,
            "PERIOD_1MONTH":   pylast.PERIOD_1MONTH,
            "PERIOD_3MONTHS":  pylast.PERIOD_3MONTHS,
            "PERIOD_6MONTHS":  pylast.PERIOD_6MONTHS,
            "PERIOD_12MONTHS": pylast.PERIOD_12MONTHS,
        }
        resolved_period = period_map.get(period, pylast.PERIOD_OVERALL)
        user = network.get_user(username)
        items = user.get_top_artists(period=resolved_period, limit=limit)
        results = []
        for item in items:
            try:
                results.append({
                    "name":      item.item.get_name(),
                    "playcount": int(item.weight),
                })
            except Exception:
                continue
        return results
    except Exception:
        return []


def recent_tracks(
    network,
    username: str,
    limit: int = 200,
) -> list[dict]:
    """
    Fetch a user's recently played tracks from Last.fm.

    Args:
        network:  pylast.LastFMNetwork instance.
        username: Last.fm username.
        limit:    Maximum number of tracks to return.

    Returns:
        List of dicts: [{title, artist, timestamp}, ...]
    """
    if network is None:
        return []
    try:
        user = network.get_user(username)
        items = user.get_recent_tracks(limit=limit)
        results = []
        for item in items:
            try:
                results.append({
                    "title":     item.track.get_name(),
                    "artist":    item.track.get_artist().get_name(),
                    "timestamp": getattr(item, "timestamp", None),
                })
            except Exception:
                continue
        return results
    except Exception:
        return []


def listening_stats(network, username: str) -> dict:
    """
    Return a summary of a user's Last.fm listening stats.

    Args:
        network:  pylast.LastFMNetwork instance.
        username: Last.fm username.

    Returns:
        Dict with keys: playcount, track_count, artist_count, album_count,
        country, registered (ISO string). Empty dict on failure.
    """
    if network is None:
        return {}
    try:
        user = network.get_user(username)
        playcount    = user.get_playcount()
        track_count  = user.get_track_count() if hasattr(user, "get_track_count") else 0
        artist_count = user.get_artist_count() if hasattr(user, "get_artist_count") else 0
        album_count  = user.get_album_count() if hasattr(user, "get_album_count") else 0
        country = ""
        try:
            country = user.get_country().get_name()
        except Exception:
            pass
        registered = ""
        try:
            reg = user.get_registered()
            registered = str(reg)
        except Exception:
            pass
        return {
            "playcount":    playcount,
            "track_count":  track_count,
            "artist_count": artist_count,
            "album_count":  album_count,
            "country":      country,
            "registered":   registered,
        }
    except Exception:
        return {}


def track_top_tags(network, artist: str, title: str, limit: int = 10) -> dict[str, float]:
    """
    Fetch top community tags for a track from Last.fm.

    Tags like "melancholy", "driving", "late night", "workout" are crowd-sourced
    mood labels — the same signal as our playlist mining, but pre-aggregated.

    Args:
        network: pylast.LastFMNetwork object.
        artist:  Artist name.
        title:   Track title.
        limit:   Max tags to return.

    Returns:
        {tag_name: weight} where weight is normalized tag count [0, 1].
    """
    if network is None or not artist or not title:
        return {}
    try:
        import pylast
        track = network.get_track(artist, title)
        top_tags = track.get_top_tags(limit=limit)
        if not top_tags:
            return {}
        max_weight = max(int(t.weight) for t in top_tags) or 1
        return {
            t.item.get_name().lower().replace(" ", "_"): round(int(t.weight) / max_weight, 4)
            for t in top_tags
            if t.item and t.item.get_name()
        }
    except Exception:
        return {}


def artist_top_tags(network, artist: str, limit: int = 10) -> dict[str, float]:
    """
    Fetch top community tags for an artist from Last.fm.

    Args:
        network: pylast.LastFMNetwork object.
        artist:  Artist name.
        limit:   Max tags to return.

    Returns:
        {tag_name: weight} normalized.
    """
    if network is None or not artist:
        return {}
    try:
        import pylast
        a = network.get_artist(artist)
        top_tags = a.get_top_tags(limit=limit)
        if not top_tags:
            return {}
        max_weight = max(int(t.weight) for t in top_tags) or 1
        return {
            t.item.get_name().lower().replace(" ", "_"): round(int(t.weight) / max_weight, 4)
            for t in top_tags
            if t.item and t.item.get_name()
        }
    except Exception:
        return {}


def enrich_library_tags(
    network,
    tracks: list[dict],
    limit_per_track: int = 5,
    max_tracks: int = 300,
) -> dict[str, dict[str, float]]:
    """
    Batch-enrich a list of tracks with Last.fm community tags.

    Processes up to max_tracks. Results are not cached here — caller
    should integrate into the profile layer.

    Args:
        network:         pylast.LastFMNetwork object.
        tracks:          List of Spotify track dicts.
        limit_per_track: Tags to fetch per track.
        max_tracks:      Cap to avoid rate limiting.

    Returns:
        {spotify_uri: {tag: weight}} for enriched tracks.
    """
    if network is None:
        return {}

    result: dict[str, dict[str, float]] = {}
    processed = 0

    for track in tracks:
        if processed >= max_tracks:
            break
        uri = track.get("uri", "")
        name = track.get("name", "")
        artists = track.get("artists", [])
        artist_name = artists[0].get("name", "") if artists else ""

        if not uri or not name or not artist_name:
            continue

        tags = track_top_tags(network, artist_name, name, limit=limit_per_track)
        if tags:
            result[uri] = tags
        processed += 1

    return result
