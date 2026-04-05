"""
ingest.py — Collect all user music from Spotify.

Pulls from every configured source and returns a deduplicated
flat list of track dicts plus metadata about origin.
"""

import time
import logging
import spotipy


def _paginate(fn, *args, limit=50, **kwargs) -> list:
    results, offset = [], 0
    while True:
        batch = fn(*args, limit=limit, offset=offset, **kwargs)
        items = batch.get("items", [])
        if not items:
            break
        results.extend(items)
        if not batch.get("next"):
            break
        offset += limit
        time.sleep(0.08)
    return results


def _normalize(items: list) -> list[dict]:
    """Unwrap saved-track wrappers {track: {...}} into plain track dicts."""
    result = []
    for item in items:
        if not item:
            continue
        t = item.get("track") if "track" in item else item
        if t and isinstance(t, dict) and t.get("uri"):
            result.append(t)
    return result


def liked_songs(sp: spotipy.Spotify) -> list[dict]:
    print("  liked songs...", end="", flush=True)
    raw = _paginate(sp.current_user_saved_tracks)
    tracks = _normalize(raw)
    print(f"\r  liked songs          {len(tracks)}")
    return tracks


def top_tracks(sp: spotipy.Spotify) -> list[dict]:
    seen, tracks = set(), []
    for term in ["short_term", "medium_term", "long_term"]:
        for t in sp.current_user_top_tracks(limit=50, time_range=term)["items"]:
            if t["uri"] not in seen:
                seen.add(t["uri"])
                tracks.append(t)
    print(f"  top tracks           {len(tracks)}")
    return tracks


def top_artists(sp: spotipy.Spotify) -> list[dict]:
    seen, artists = set(), []
    for term in ["short_term", "medium_term", "long_term"]:
        for a in sp.current_user_top_artists(limit=50, time_range=term)["items"]:
            if a["id"] not in seen:
                seen.add(a["id"])
                artists.append(a)
    print(f"  top artists          {len(artists)}")
    return artists


def followed_artist_tracks(
    sp: spotipy.Spotify,
    n: int = 3,
    market: str | None = None,
) -> list[dict]:
    """
    Fetch top-N tracks from each followed artist.

    market: the user's own Spotify country code (e.g. "DE", "FR").
            Using the user's actual market avoids 403s from market-restricted
            content.  Defaults to None which lets Spotify use the token's
            implicit market.  Never hardcode "US" — that breaks for every
            non-US account and causes 403s in Dev Mode.
    """
    followed, after = [], None
    while True:
        kw = {"limit": 50}
        if after:
            kw["after"] = after
        data = sp.current_user_followed_artists(**kw).get("artists", {})
        items = data.get("items", [])
        if not items:
            break
        followed.extend(items)
        after = data.get("cursors", {}).get("after")
        if not after:
            break
        time.sleep(0.08)

    # Suppress spotipy's HTTP-level 403 log spam: artist/top-tracks is
    # blocked in Dev Mode regardless of market — the exception is already
    # caught below so the output is pure noise.
    _sp_log = logging.getLogger("spotipy.client")
    _prev_level = _sp_log.level
    _sp_log.setLevel(logging.CRITICAL)

    tracks, seen = [], set()
    blocked_count = 0
    for artist in followed:
        try:
            # Use the user's own market; if none provided Spotify picks from token
            kw_tt = {}
            if market:
                kw_tt["country"] = market
            result = sp.artist_top_tracks(artist["id"], **kw_tt)
            for t in (result.get("tracks") or [])[:n]:
                if t.get("uri") and t["uri"] not in seen:
                    seen.add(t["uri"])
                    tracks.append(t)
        except spotipy.SpotifyException as exc:
            if exc.http_status == 403:
                blocked_count += 1
                if blocked_count >= 5:
                    # Endpoint is universally blocked in this session — bail out
                    break
            # else: other error, skip this artist silently
        except Exception:
            pass
        time.sleep(0.05)

    _sp_log.setLevel(_prev_level)

    if blocked_count >= 5:
        print(f"  followed artists     [blocked by Spotify Dev Mode — endpoint restricted]")
    else:
        print(f"  followed artists     {len(tracks)} tracks from {len(followed)} artists")
    return tracks


def saved_playlist_tracks(sp: spotipy.Spotify) -> list[dict]:
    # In Spotify Dev Mode, playlist_items returns 403 for playlists owned by
    # users not registered in the app.  Only read playlists the current user
    # actually OWNS — followed/saved playlists from other users will 403.
    try:
        user_id = sp.current_user()["id"]
    except Exception:
        user_id = None

    playlists = _paginate(sp.current_user_playlists)

    # Filter to user-owned playlists only (avoids mass 403 spam in Dev Mode)
    if user_id:
        owned = [pl for pl in playlists if pl.get("owner", {}).get("id") == user_id]
    else:
        owned = playlists  # fallback: try all (will 403 on others' playlists)

    tracks, seen = [], set()
    consec_403 = 0
    for pl in owned:
        try:
            items = _paginate(sp.playlist_items, pl["id"], additional_types=["track"])
            consec_403 = 0
            for item in items:
                t = item.get("track")
                if t and t.get("uri") and t["uri"] not in seen:
                    seen.add(t["uri"])
                    tracks.append(t)
        except Exception as e:
            err_str = str(e)
            if "403" in err_str or "Forbidden" in err_str:
                consec_403 += 1
                if consec_403 >= 3:
                    # Spotify is blocking all playlist reads — bail out early
                    print(f"\n  [warn] playlist_items blocked (Dev Mode) — skipping remaining")
                    break
            # else ignore other errors
        time.sleep(0.08)

    print(f"  saved playlists      {len(tracks)} tracks from {len(owned)} owned ({len(playlists)} total)")
    return tracks


def friend_playlist_tracks(sp: spotipy.Spotify, urls: list[str]) -> list[dict]:
    tracks, seen = [], set()
    for url in urls:
        try:
            pid = url.split("/playlist/")[-1].split("?")[0]
            items = _paginate(sp.playlist_items, pid, additional_types=["track"])
            count = 0
            for item in items:
                t = item.get("track")
                if t and t.get("uri") and t["uri"] not in seen:
                    seen.add(t["uri"])
                    tracks.append(t)
                    count += 1
            print(f"  friend playlist      {count} tracks (...{pid[-8:]})")
        except Exception as e:
            print(f"  friend playlist      ERROR: {e}")
        time.sleep(0.1)
    return tracks


def collect(sp: spotipy.Spotify, cfg) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Master ingest. Returns:
      all_tracks   — deduplicated flat list of every track from all sources
      top_tracks   — just the user's top-played tracks
      top_artists  — user's top artists
    """
    print("\n  Collecting your library:")
    all_raw: list[dict] = []

    # Fetch user profile once to get their market/country.
    # This is used for country-specific endpoints (artist top-tracks).
    # Using the user's own market avoids cross-region 403s.
    _user_market: str | None = None
    try:
        _me = sp.current_user()
        _user_market = (_me.get("country") or "").strip() or None
    except Exception:
        pass

    liked = liked_songs(sp)
    all_raw.extend(liked)

    t_tracks = top_tracks(sp)
    all_raw.extend(t_tracks)

    t_artists = top_artists(sp)

    if getattr(cfg, "INCLUDE_FOLLOWED_ARTISTS", True):
        all_raw.extend(
            followed_artist_tracks(
                sp,
                getattr(cfg, "FOLLOWED_ARTIST_TOP_N", 3),
                market=_user_market,
            )
        )

    if getattr(cfg, "INCLUDE_SAVED_PLAYLISTS", True):
        all_raw.extend(saved_playlist_tracks(sp))

    urls = getattr(cfg, "FRIEND_PLAYLIST_URLS", [])
    if urls:
        all_raw.extend(friend_playlist_tracks(sp, urls))

    # Deduplicate by URI
    seen: set[str] = set()
    all_tracks: list[dict] = []
    for t in all_raw:
        if t and t.get("uri") and t["uri"] not in seen:
            seen.add(t["uri"])
            all_tracks.append(t)

    print(f"\n  Total unique tracks: {len(all_tracks)}")
    return all_tracks, t_tracks, t_artists
