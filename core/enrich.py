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
import re
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
    Spotify deprecated GET /audio-features in Nov 2024 — always returns 403.
    Stub returns empty dict. Scoring falls back to metadata proxy (W_METADATA_AUDIO).
    """
    return {}


# ── Track metadata signals (M1.5) ─────────────────────────────────────────────

# Title keyword patterns → (tag_name, weight)
_TITLE_PATTERNS: list[tuple] = [
    (re.compile(r"\b(midnight|3\s?am|2\s?am|night)\b",    re.I), "night",   0.4),
    (re.compile(r"\b(morning|sunrise|dawn|wake\s?up)\b",  re.I), "morning", 0.4),
    (re.compile(r"\b(love|heart|darling|baby|babe)\b",    re.I), "love",    0.3),
    (re.compile(r"\b(rage|fury|war|fight|battle)\b",      re.I), "angry",   0.3),
    (re.compile(r"\b(drive|road|highway|car|cruise)\b",   re.I), "drive",   0.3),
    (re.compile(r"\b(rain|storm|cloud|grey|gray|fog)\b",  re.I), "moody",   0.3),
    (re.compile(r"\b(intro|opening|prelude)\b",           re.I), None,      0.0),  # meta_intro
    (re.compile(r"\b(outro|finale|end|closing)\b",        re.I), None,      0.0),  # meta_outro
    (re.compile(r"\b(skit|interlude|reprise)\b",          re.I), None,      0.0),  # meta_interlude
]


def _extract_metadata_signals(track: dict) -> dict[str, float]:
    """
    Extract zero-cost mood signals from a Spotify track dict.

    Runs for 100% of library tracks — no API calls, sub-second total.
    All inputs come from the existing Spotify track object already in snapshot.

    Returns {tag: weight} dict of signals. Tags prefixed with "meta_" are
    structural signals; others (night, morning, love, etc.) align directly
    with packs.json expected_tags vocabulary.
    """
    signals: dict[str, float] = {}
    name       = (track.get("name") or "").strip()
    duration   = track.get("duration_ms") or 0
    explicit   = track.get("explicit", False)
    track_num  = track.get("track_number") or 0
    artists    = track.get("artists") or []
    album      = track.get("album") or {}
    album_type = (album.get("album_type") or "").lower()
    total_trk  = album.get("total_tracks") or 0

    # Structural / positional signals
    if explicit:
        signals["meta_explicit"] = 0.4

    if album_type == "single":
        signals["meta_single"] = 0.3

    if album_type == "album" and track_num == 1:
        signals["meta_opener"] = 0.4

    if album_type == "album" and total_trk > 1 and track_num == total_trk:
        signals["meta_closer"] = 0.4

    if duration > 0:
        if duration > 480_000:   # > 8 minutes
            signals["meta_epic"] = 0.5
        if duration < 90_000:    # < 90 seconds
            signals["meta_interlude"] = 0.7

    # Featuring artist detection
    feat_pattern = re.compile(r"\b(feat\.?|ft\.?|featuring|with)\s+\S", re.I)
    has_feat = (
        len(artists) > 1
        or bool(feat_pattern.search(name))
        or bool(feat_pattern.search(album.get("name") or ""))
    )
    if has_feat:
        signals["meta_feature"] = 0.3

    # Title keyword patterns
    title_lower = name.lower()
    if re.search(r"\b(intro|opening|prelude)\b", title_lower):
        signals["meta_intro"] = 0.6
    if re.search(r"\b(outro|finale|closing)\b", title_lower):
        signals["meta_outro"] = 0.6
    if re.search(r"\b(skit|interlude|reprise)\b", title_lower) or (
        0 < duration < 90_000
    ):
        signals.setdefault("meta_interlude", 0.7)

    # Vocabulary signals (align with packs.json expected_tags)
    for _pattern, tag, weight in _TITLE_PATTERNS:
        if tag and tag not in signals and _pattern.search(name):
            signals[tag] = weight

    return signals


def enrich_metadata(tracks: list[dict]) -> dict[str, dict[str, float]]:
    """
    Run _extract_metadata_signals for all tracks. Zero API calls.

    Returns:
        {uri: {tag: weight}} for all tracks that have a URI.
        Only tracks with at least one signal are included.
    """
    result: dict[str, dict] = {}
    for track in tracks:
        uri = track.get("uri", "")
        if not uri:
            continue
        sigs = _extract_metadata_signals(track)
        if sigs:
            result[uri] = sigs
    return result


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
    _print(f"  Audio features skipped (deprecated endpoint — {len(uris)} tracks use metadata proxy)")
    feats = audio_features(sp, uris)

    return genres, feats
