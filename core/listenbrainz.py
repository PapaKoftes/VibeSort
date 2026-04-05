"""
listenbrainz.py — ListenBrainz integration.

ListenBrainz is the open-source, privacy-respecting alternative to Last.fm.
It provides full listening history, similar artist recommendations, and
community-driven music data.

Requires: liblistenbrainz >= 0.7.0  (pip install liblistenbrainz)
Token: get a free token at listenbrainz.org/settings/

API contract (v0.7.0):
  - get_listens()          → list[Listen]  (Listen has direct attrs, no .track_metadata)
  - get_user_artists()     → dict  {"payload": {"artists": [...]}}
  - get_user_recordings()  → dict  {"payload": {"recordings": [...]}}
  - get_user_listen_count()→ int
"""

from __future__ import annotations
from typing import Optional


def connect(token: str) -> Optional[object]:
    """
    Connect to ListenBrainz with a user token.

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
        # v0.7.0: use a lightweight ping — get own listen count requires no auth,
        # but using get_user_listen_count confirms token works.
        count = client.get_user_listen_count(_get_username(client))
        return isinstance(count, int)
    except Exception:
        return False


def _get_username(client) -> str:
    """Extract username from client (stored after set_auth_token in v0.7.0)."""
    # The client stores the username associated with the token
    return getattr(client, "auth_token_username", "") or getattr(client, "username", "") or ""


def recent_listens(client, username: str, count: int = 200) -> list[dict]:
    """
    Fetch recent listens for a user.

    Returns:
        List of listen dicts with keys: artist, title, timestamp, isrc, spotify_id.
    """
    if client is None:
        return []
    try:
        listens = client.get_listens(username=username, count=min(count, 200))
        result = []
        for listen in listens:
            # v0.7.0: Listen has direct attributes (no .track_metadata)
            result.append({
                "artist":     getattr(listen, "artist_name", "") or "",
                "title":      getattr(listen, "track_name",  "") or "",
                "timestamp":  getattr(listen, "listened_at", None),
                "isrc":       getattr(listen, "isrc",        "") or "",
                "spotify_id": getattr(listen, "spotify_id",  "") or "",
            })
        return result
    except Exception:
        return []


def top_artists(client, username: str, count: int = 50) -> list[dict]:
    """
    Fetch top artists for a user from ListenBrainz stats.

    Returns:
        List of dicts with keys: artist, listen_count, mbid.
    """
    if client is None:
        return []
    try:
        # v0.7.0: returns dict {"payload": {"artists": [...], ...}}
        response = client.get_user_artists(username=username, count=min(count, 200))
        artists = _payload_list(response, "artists")
        return [
            {
                "artist":       a.get("artist_name", ""),
                "listen_count": a.get("listen_count", 0),
                "mbid":         a.get("artist_mbid", ""),
            }
            for a in artists
        ]
    except Exception:
        return []


def top_tracks(client, username: str, count: int = 100) -> list[dict]:
    """
    Fetch top tracks for a user from ListenBrainz stats.

    Returns:
        List of dicts with keys: artist, title, listen_count, mbid.
    """
    if client is None:
        return []
    try:
        # v0.7.0: returns dict {"payload": {"recordings": [...], ...}}
        response = client.get_user_recordings(username=username, count=min(count, 200))
        recordings = _payload_list(response, "recordings")
        return [
            {
                "artist":       r.get("artist_name", ""),
                "title":        r.get("track_name",  ""),
                "listen_count": r.get("listen_count", 0),
                "mbid":         r.get("recording_mbid", ""),
            }
            for r in recordings
        ]
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
        result = client.get_similar_artists(
            artist_mbid=artist_mbid, algorithm="session_based", count=count
        )
        names = []
        if hasattr(result, "artists"):
            for a in result.artists:
                name = getattr(a, "name", "")
                if name:
                    names.append(name)
        elif isinstance(result, dict):
            for a in _payload_list(result, "artists"):
                name = a.get("artist_name") or a.get("name", "")
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
    stats: dict = {}

    try:
        count = client.get_user_listen_count(username)
        stats["total_listens"] = int(count) if isinstance(count, (int, float)) else 0
    except Exception:
        stats["total_listens"] = 0

    try:
        artists = top_artists(client, username, count=1)
        if artists:
            stats["top_artist"] = artists[0].get("artist", "")
    except Exception:
        pass

    try:
        tracks = top_tracks(client, username, count=1)
        if tracks:
            t = tracks[0]
            stats["top_track"] = f"{t.get('title', '')} — {t.get('artist', '')}"
    except Exception:
        pass

    return stats


# ── Helpers ───────────────────────────────────────────────────────────────────

def _payload_list(response: dict, key: str) -> list:
    """Extract list from ListenBrainz v0.7.0 response dict.

    The response is always {"payload": {key: [...], ...}}.
    """
    if not isinstance(response, dict):
        return []
    payload = response.get("payload", response)  # handle both shapes gracefully
    items = payload.get(key, [])
    return items if isinstance(items, list) else []
