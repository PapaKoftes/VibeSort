"""
enrich.py — Add audio features and artist genre data to tracks.

NOTE: Spotify deprecated GET /audio-features (Nov 2024) and restricts
GET /artists batch lookup for Development-Mode apps.  Both calls degrade
gracefully — empty dicts are returned on 403/error and the scorer falls
back to tag-based + genre-based signals only.

Dev Mode often blocks batch /artists (403); we fall back to per-id calls plus
a capped /search fallback. Those bursts can hit Spotify 429 — we pace requests,
abort further Spotify genre calls on 429, and persist a disk cache so rescans
do not re-fetch every artist.
"""

from __future__ import annotations

import collections
import json
import logging
import os
import sys
import time
import spotipy


def _print(*args, **kwargs) -> None:
    """Safe print that survives non-TTY stdout (Streamlit, pipes, Windows)."""
    try:
        print(*args, **kwargs)
    except (OSError, UnicodeEncodeError):
        try:
            kwargs.pop("end", None)
            kwargs.pop("flush", None)
            print(*args, file=sys.stderr)
        except Exception:
            pass


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPOTIFY_GENRE_CACHE = os.path.join(_ROOT, "outputs", ".spotify_genres_cache.json")

# When batch /artists is blocked, stay well under Spotify Web API rate limits.
_INDIVIDUAL_ARTIST_DELAY = float(os.getenv("SPOTIFY_ARTIST_GENRE_DELAY", "0.35"))
_SEARCH_GENRE_DELAY = float(os.getenv("SPOTIFY_SEARCH_GENRE_DELAY", "0.4"))
_MAX_INDIVIDUAL_FALLBACK = int(os.getenv("SPOTIFY_INDIVIDUAL_ARTISTS_CAP", "100"))
_MAX_SEARCH_FALLBACK = int(os.getenv("SPOTIFY_SEARCH_GENRES_CAP", "50"))

# Spotipy logs HTTP errors at WARNING level before raising — suppress that
# spam for the specific endpoints we KNOW are blocked in Dev Mode (403 is
# expected and already handled gracefully in the code below).
_sp_log = logging.getLogger("spotipy.client")


def _retry_after_seconds(exc: spotipy.SpotifyException) -> int | None:
    h = exc.headers or {}
    raw = h.get("Retry-After") or h.get("retry-after")
    if raw is None:
        return None
    try:
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return None


def _format_retry_human(sec: int) -> str:
    if sec >= 3600:
        return f"{sec // 3600}h {(sec % 3600) // 60}m"
    if sec >= 60:
        return f"{sec // 60}m {sec % 60}s"
    return f"{sec}s"


def _load_genre_disk_cache() -> dict[str, list[str]]:
    try:
        if os.path.exists(_SPOTIFY_GENRE_CACHE):
            with open(_SPOTIFY_GENRE_CACHE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): list(v) for k, v in data.items() if isinstance(v, list)}
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {}


def _save_genre_disk_cache(cache: dict[str, list[str]]) -> None:
    try:
        os.makedirs(os.path.dirname(_SPOTIFY_GENRE_CACHE), exist_ok=True)
        with open(_SPOTIFY_GENRE_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except OSError:
        pass


def artist_genres(
    sp: spotipy.Spotify,
    artist_ids: list[str],
    id_name_map: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    """
    Returns {artist_id: [genre, ...]} for all given IDs.

    Strategy:
      1. Try batched GET /artists?ids= (50 at a time) — fast but 403'd in Dev Mode.
      2. On 403, fall back to individual GET /artists/{id} (capped, slow-paced).
      3. Optional /search fallback for IDs still empty (small cap, slow-paced).
      On 429, stop immediately — do not chain hundreds of calls (avoids day-long
      Retry-After locks). Deezer / Last.fm / AudioDB still enrich genres later.
    """
    result: dict[str, list[str]] = {}
    ids = list(set(artist_ids))
    batch_blocked = False
    hit_rate_limit = False

    # Suppress HTTP-level 403 log spam — batch /artists endpoint is universally
    # blocked in Dev Mode; the exception is caught and handled below.
    _prev = _sp_log.level
    _sp_log.setLevel(logging.CRITICAL)

    for i in range(0, len(ids), 50):
        try:
            batch = sp.artists(ids[i:i+50])
            for a in (batch or {}).get("artists", []):
                if a:
                    result[a["id"]] = a.get("genres", [])
        except spotipy.SpotifyException as exc:
            if exc.http_status == 429:
                _sp_log.setLevel(_prev)
                ra = _retry_after_seconds(exc)
                rh = _format_retry_human(ra) if ra is not None else "unknown"
                _hint = ""
                if ra is not None and ra >= 3600:
                    _hint = (
                        " Long waits usually mean the app hit a quota ceiling. "
                        "This scan still continues with Deezer/AudioDB/etc.; "
                        "cached Spotify genres are reused on the next scan."
                    )
                print(
                    f"\n  [error] Spotify rate limited (429) on batch artist lookup. "
                    f"Stopping Spotify genre fetch. Retry-After: ~{rh}.{_hint}"
                )
                return result
            if exc.http_status == 403:
                _sp_log.setLevel(_prev)
                print(
                    f"\n  [warn] batch artist lookup blocked (403) — "
                    f"falling back to individual calls (max {_MAX_INDIVIDUAL_FALLBACK}, "
                    f"{_INDIVIDUAL_ARTIST_DELAY}s spacing)..."
                )
                batch_blocked = True
                break
            _sp_log.setLevel(_prev)
            raise
        time.sleep(0.08)

    _sp_log.setLevel(_prev)

    if batch_blocked:
        remaining = [aid for aid in ids if aid not in result]
        fetched_individual = 0
        _sp_log.setLevel(logging.CRITICAL)
        for aid in remaining[:_MAX_INDIVIDUAL_FALLBACK]:
            try:
                a = sp.artist(aid)
                if a:
                    result[aid] = a.get("genres", [])
                    fetched_individual += 1
            except spotipy.SpotifyException as exc:
                if exc.http_status == 429:
                    ra = _retry_after_seconds(exc)
                    rh = _format_retry_human(ra) if ra is not None else "unknown"
                    _hint = (
                        " Next scan loads cached IDs from outputs/.spotify_genres_cache.json "
                        "and only fetches missing artists (slower pacing, smaller caps)."
                        if ra is not None and ra >= 3600
                        else ""
                    )
                    print(
                        f"\n  [error] Spotify rate limited (429) during individual artist lookup "
                        f"after {fetched_individual} OK. Retry-After: ~{rh}. "
                        f"Skipping further Spotify genre calls this scan.{_hint}"
                    )
                    hit_rate_limit = True
                    break
            except Exception:
                pass
            time.sleep(_INDIVIDUAL_ARTIST_DELAY)
        _sp_log.setLevel(_prev)
        if fetched_individual:
            print(f"  [info] individual artist fallback: {fetched_individual} artists retrieved")
        elif not hit_rate_limit:
            print("  [warn] individual artist lookup also blocked — no genre data available")

    # Tier 3: Spotify search fallback (only if we did not just 429)
    if id_name_map and batch_blocked and not hit_rate_limit:
        _still_empty = [
            aid for aid in ids
            if not result.get(aid) and id_name_map.get(aid)
        ]
        _search_added = 0
        _sp_log.setLevel(logging.CRITICAL)
        for aid in _still_empty[:_MAX_SEARCH_FALLBACK]:
            name = id_name_map[aid]
            try:
                res = sp.search(q=f'artist:"{name}"', type="artist", limit=1)
                items = ((res or {}).get("artists") or {}).get("items") or []
                for item in items:
                    if item and item.get("id") == aid:
                        genres = item.get("genres") or []
                        if genres:
                            result[aid] = genres
                            _search_added += 1
                        break
            except spotipy.SpotifyException as exc:
                if exc.http_status == 429:
                    ra = _retry_after_seconds(exc)
                    rh = _format_retry_human(ra) if ra is not None else "unknown"
                    print(
                        f"\n  [error] Spotify rate limited (429) during search genre fallback "
                        f"after {_search_added} OK. Retry-After: ~{rh}."
                    )
                    hit_rate_limit = True
                    break
            except Exception:
                pass
            time.sleep(_SEARCH_GENRE_DELAY)
        _sp_log.setLevel(_prev)
        if _search_added:
            print(f"  [info] search genre fallback: {_search_added} artists enriched via /search")

    return result


def audio_features(sp: spotipy.Spotify, track_uris: list[str]) -> dict[str, dict]:
    """
    Returns {uri: feature_dict} for all given track URIs (batched, 100 at a time).
    Returns an empty dict silently on 403 — Spotify deprecated this endpoint
    in Nov 2024; profile.py falls back to a neutral [0.5]*6 audio vector.
    """
    features: dict[str, dict] = {}
    ids = [u.split(":")[-1] for u in track_uris if u.startswith("spotify:track:")]

    # Suppress the 403 log spam — this endpoint is deprecated and always 403s;
    # the exception is caught below and the code continues with no audio features.
    _prev = _sp_log.level
    _sp_log.setLevel(logging.CRITICAL)

    for i in range(0, len(ids), 100):
        try:
            batch = sp.audio_features(ids[i:i+100]) or []
            for f in batch:
                if f:
                    features[f"spotify:track:{f['id']}"] = f
        except spotipy.SpotifyException as exc:
            if exc.http_status in (403, 429):
                print(f"\n  [warn] audio features skipped ({exc.http_status}) — "
                      "Spotify deprecated this endpoint; scoring on tags/genres only")
                break
            _sp_log.setLevel(_prev)
            raise
        time.sleep(0.08)

    _sp_log.setLevel(_prev)
    return features


def gather(
    sp: spotipy.Spotify,
    tracks: list[dict],
    seed_genres: dict[str, list[str]] | None = None,
) -> tuple[dict[str, list[str]], dict[str, dict]]:
    """
    Convenience: fetch both artist genres and audio features for a track list.
    Returns (artist_genres_map, audio_features_map).
    Either map may be empty if Spotify's API returns 403 — callers must handle this.

    seed_genres: pre-populated {artist_id: [genre, ...]} from top_artists/followed
                 artists already in memory (no extra API calls needed).  These are
                 merged in BEFORE the batch lookup so we always have data for the
                 user's most-listened artists even if the batch endpoint is blocked.
    """
    # Pre-populate from seed (top_artists data already fetched during ingest —
    # no extra API calls).  This covers the user's ~150 most-listened artists
    # even when the batch /artists endpoint returns 403 in Dev Mode.
    genres: dict[str, list[str]] = dict(seed_genres) if seed_genres else {}

    disk_cache = _load_genre_disk_cache()
    if disk_cache:
        _from_disk = 0
        for aid, glist in disk_cache.items():
            if aid not in genres and glist:
                genres[aid] = glist
                _from_disk += 1
        if _from_disk:
            print(f"  Spotify genre cache   {_from_disk} artists loaded from disk")

    # Count how often each artist appears in the library so the individual-
    # fallback cap hits the most important artists first.
    # Build name map simultaneously for the search fallback tier.
    artist_freq: dict[str, int] = collections.defaultdict(int)
    artist_names: dict[str, str] = {}
    for t in tracks:
        for a in t.get("artists", []):
            aid = a.get("id", "")
            if aid:
                artist_freq[aid] += 1
                if not artist_names.get(aid) and a.get("name"):
                    artist_names[aid] = a["name"]

    missing = sorted(
        [aid for aid in artist_freq if not genres.get(aid)],
        key=lambda aid: -artist_freq[aid],
    )
    batch_ok = False
    if missing:
        _print(f"  Fetching genre data   ({len(missing)} artists not in seed/cache)...")
        fetched = artist_genres(sp, missing, id_name_map=artist_names)
        genres.update(fetched)
        batch_ok = bool(fetched)

    # Persist any resolved genres so rescans skip Spotify for those IDs.
    for aid, glist in genres.items():
        if glist:
            disk_cache[aid] = glist
    _save_genre_disk_cache(disk_cache)

    nonempty = sum(1 for v in genres.values() if v)
    source   = "seed+batch" if batch_ok else ("seed only" if genres else "unavailable")
    _print(f"  Genre data            {nonempty}/{len(genres)} artists have genres ({source})")

    uris = [t["uri"] for t in tracks if t.get("uri")]
    _print(f"  Fetching audio features ({len(uris)} tracks)...")
    feats = audio_features(sp, uris)
    _print(f"  Audio features        {len(feats)} tracks"
           f"{' (unavailable — deprecated)' if not feats else ''}")

    return genres, feats
