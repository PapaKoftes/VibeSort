"""
listenbrainz.py — ListenBrainz integration.

ListenBrainz is the open-source, privacy-respecting alternative to Last.fm.
It provides full listening history, similar artist recommendations, and
community-driven music data.

Requires: liblistenbrainz (pip install liblistenbrainz)
Token: get a free token at listenbrainz.org/settings/
"""

import os
from typing import Optional


def connect(token: str) -> Optional[object]:
    """
    Connect to ListenBrainz with a user token.

    Args:
        token: ListenBrainz user token from listenbrainz.org/settings/

    Returns:
        ListenBrainz client object or None if lib not installed / token invalid.
    """
    if not token:
        return None
    try:
        import liblistenbrainz
        client = liblistenbrainz.ListenBrainz()
        client.set_auth_token(token)
        return client
    except ImportError:
        return None
    except Exception:
        return None


def is_connected(client) -> bool:
    """Check if the client is authenticated and working."""
    if client is None:
        return False
    try:
        client.is_token_valid(client.auth_token)
        return True
    except Exception:
        return False


def recent_listens(client, username: str, count: int = 200) -> list[dict]:
    """
    Fetch recent listens for a user.

    Args:
        client:   ListenBrainz client.
        username: ListenBrainz username.
        count:    Number of recent listens to fetch.

    Returns:
        List of listen dicts with keys: artist, title, timestamp.
    """
    if client is None:
        return []
    try:
        listens = client.get_listens(username=username, count=min(count, 200))
        result = []
        for listen in listens:
            ti = listen.track_metadata
            result.append({
                "artist": ti.artist_name if hasattr(ti, "artist_name") else "",
                "title":  ti.track_name  if hasattr(ti, "track_name")  else "",
                "timestamp": listen.listened_at if hasattr(listen, "listened_at") else None,
            })
        return result
    except Exception:
        return []


def top_artists(client, username: str, count: int = 50) -> list[dict]:
    """
    Fetch top artists for a user from ListenBrainz stats.

    Args:
        client:   ListenBrainz client.
        username: ListenBrainz username.
        count:    Number of artists to return.

    Returns:
        List of dicts with keys: artist, listen_count.
    """
    if client is None:
        return []
    try:
        stats = client.get_user_artists(username=username, count=min(count, 200))
        result = []
        if hasattr(stats, "artists"):
            for a in stats.artists:
                result.append({
                    "artist":       getattr(a, "artist_name", ""),
                    "listen_count": getattr(a, "listen_count", 0),
                })
        return result
    except Exception:
        return []


def top_tracks(client, username: str, count: int = 100) -> list[dict]:
    """
    Fetch top tracks for a user from ListenBrainz stats.

    Returns:
        List of dicts with keys: artist, title, listen_count.
    """
    if client is None:
        return []
    try:
        stats = client.get_user_recordings(username=username, count=min(count, 200))
        result = []
        if hasattr(stats, "recordings"):
            for r in stats.recordings:
                result.append({
                    "artist":       getattr(r, "artist_name", ""),
                    "title":        getattr(r, "track_name", ""),
                    "listen_count": getattr(r, "listen_count", 0),
                })
        return result
    except Exception:
        return []


def similar_artists(client, artist_mbid: str, count: int = 10) -> list[str]:
    """
    Get similar artists by MusicBrainz ID.

    Returns:
        List of similar artist name strings.
    """
    if client is None or not artist_mbid:
        return []
    try:
        result = client.get_similar_artists(artist_mbid=artist_mbid, algorithm="session_based", count=count)
        names = []
        if hasattr(result, "artists"):
            for a in result.artists:
                name = getattr(a, "name", "")
                if name:
                    names.append(name)
        return names
    except Exception:
        return []


def listening_stats(client, username: str) -> dict:
    """
    Get summary listening stats for a user.

    Returns:
        Dict with keys: total_listens, top_artist, top_track.
    """
    if client is None:
        return {}
    try:
        stats = {}
        # Total listen count
        try:
            count_data = client.get_listen_count(username=username)
            stats["total_listens"] = getattr(count_data, "count", 0)
        except Exception:
            stats["total_listens"] = 0

        # Top artist
        artists = top_artists(client, username, count=1)
        if artists:
            stats["top_artist"] = artists[0].get("artist", "")

        # Top track
        tracks = top_tracks(client, username, count=1)
        if tracks:
            stats["top_track"] = f"{tracks[0].get('title', '')} — {tracks[0].get('artist', '')}"

        return stats
    except Exception:
        return {}
