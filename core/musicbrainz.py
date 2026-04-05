"""
musicbrainz.py — MusicBrainz genre and mood tag enrichment.

MusicBrainz is a human-curated music encyclopedia with recording-level
genre and mood tags. It fills gaps where Spotify's genre tags are vague
or missing — especially for niche, underground, and non-English music.

Tags are returned in the same {tag: weight} format as playlist mining.
Results are cached permanently to outputs/.mb_cache.json.

Rate limit: 1 req/sec (enforced internally).
"""

import json
import os
import time
from typing import Optional

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".mb_cache.json")
_cache: dict | None = None
_last_request_time: float = 0.0
MB_USER_AGENT = "Vibesort/1.0 (https://github.com/PapaKoftes/VibeSort)"


def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
            return _cache
        except (json.JSONDecodeError, OSError):
            pass
    _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except OSError:
        pass


def _rate_limit() -> None:
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 1.05:
        time.sleep(1.05 - elapsed)
    _last_request_time = time.time()


def _mb_available() -> bool:
    try:
        import musicbrainzngs
        return True
    except ImportError:
        return False


def _setup_mb() -> bool:
    if not _mb_available():
        return False
    import musicbrainzngs
    musicbrainzngs.set_useragent("Vibesort", "1.0", "https://github.com/PapaKoftes/VibeSort")
    return True


def _cache_key(artist: str, title: str) -> str:
    return f"{artist.lower().strip()}|{title.lower().strip()}"


def _tags_to_weights(tags: list[dict]) -> dict[str, float]:
    """
    Convert MusicBrainz tag list [{name, count}, ...] to {tag: weight}.
    Weight = count / max_count, normalized to [0, 1].
    """
    if not tags:
        return {}
    counts = {t["name"].lower().replace(" ", "_"): int(t.get("count", 1)) for t in tags if t.get("name")}
    if not counts:
        return {}
    max_count = max(counts.values()) or 1
    return {tag: round(count / max_count, 4) for tag, count in counts.items()}


def recording_tags(artist: str, title: str) -> dict[str, float]:
    """
    Fetch genre/mood tags for a recording from MusicBrainz.

    Searches by artist + title, takes the top result, and returns
    its tags as {tag: weight} dict.

    Args:
        artist: Artist name string.
        title:  Track title string.

    Returns:
        Dict of {tag: weight} or empty dict on failure / not found.
    """
    if not artist or not title:
        return {}

    cache = _load_cache()
    key = _cache_key(artist, title)
    if key in cache:
        return cache[key]

    if not _setup_mb():
        return {}

    import musicbrainzngs

    try:
        _rate_limit()
        result = musicbrainzngs.search_recordings(
            recording=title,
            artist=artist,
            limit=5,
        )
        recordings = result.get("recording-list", [])
        if not recordings:
            cache[key] = {}
            _save_cache()
            return {}

        # Take the highest-score result
        best = recordings[0]
        rec_id = best.get("id")
        if not rec_id:
            cache[key] = {}
            _save_cache()
            return {}

        # Fetch full recording with tags
        _rate_limit()
        rec_result = musicbrainzngs.get_recording_by_id(
            rec_id,
            includes=["tags", "artist-credits", "releases"],
        )
        recording = rec_result.get("recording", {})
        tags = recording.get("tag-list", [])
        weights = _tags_to_weights(tags)

        # If recording has no tags, try the release group tags
        if not weights and recording.get("release-list"):
            rg_id = (recording["release-list"][0]
                     .get("release-group", {})
                     .get("id"))
            if rg_id:
                _rate_limit()
                rg_result = musicbrainzngs.get_release_group_by_id(
                    rg_id, includes=["tags"]
                )
                rg_tags = rg_result.get("release-group", {}).get("tag-list", [])
                weights = _tags_to_weights(rg_tags)

        cache[key] = weights
        _save_cache()
        return weights

    except Exception:
        cache[key] = {}
        _save_cache()
        return {}


def artist_tags(artist: str) -> dict[str, float]:
    """
    Fetch genre/mood tags for an artist from MusicBrainz.

    Args:
        artist: Artist name string.

    Returns:
        Dict of {tag: weight} or empty dict on failure.
    """
    if not artist:
        return {}

    cache = _load_cache()
    key = f"artist|{artist.lower().strip()}"
    if key in cache:
        return cache[key]

    if not _setup_mb():
        return {}

    import musicbrainzngs

    try:
        _rate_limit()
        result = musicbrainzngs.search_artists(artist=artist, limit=3)
        artists = result.get("artist-list", [])
        if not artists:
            cache[key] = {}
            _save_cache()
            return {}

        best_id = artists[0].get("id")
        if not best_id:
            cache[key] = {}
            _save_cache()
            return {}

        _rate_limit()
        artist_result = musicbrainzngs.get_artist_by_id(best_id, includes=["tags"])
        tags = artist_result.get("artist", {}).get("tag-list", [])
        weights = _tags_to_weights(tags)

        cache[key] = weights
        _save_cache()
        return weights

    except Exception:
        cache[key] = {}
        _save_cache()
        return {}


def recording_tags_by_isrc(isrc: str) -> dict[str, float]:
    """
    Fetch tags for a recording using its ISRC code.

    ISRC-based lookup is more reliable than name/title search because it
    identifies the exact recording rather than relying on fuzzy text matching.
    Spotify includes ISRCs in track['external_ids']['isrc'].

    Returns {tag: weight} or empty dict on failure / not found.
    """
    if not isrc:
        return {}

    isrc = isrc.upper().strip()
    cache = _load_cache()
    key = f"isrc|{isrc}"
    if key in cache:
        return cache[key]

    if not _setup_mb():
        return {}

    import musicbrainzngs

    try:
        _rate_limit()
        result = musicbrainzngs.get_recordings_by_isrc(isrc, includes=["tags"])
        recordings = result.get("isrc", {}).get("recording-list", [])
        if not recordings:
            cache[key] = {}
            _save_cache()
            return {}

        # Prefer recording with the most tags; fall back to first result
        best = max(recordings, key=lambda r: len(r.get("tag-list", [])), default=recordings[0])
        tags = best.get("tag-list", [])
        weights = _tags_to_weights(tags)

        cache[key] = weights
        _save_cache()
        return weights

    except Exception:
        cache[key] = {}
        _save_cache()
        return {}


def enrich_tracks(tracks: list[dict], max_tracks: int = 200) -> dict[str, dict[str, float]]:
    """
    Enrich a list of track dicts with MusicBrainz tags.

    Processes up to max_tracks (rate-limited, ~1s/track).
    Skips tracks that are already in the cache.

    Args:
        tracks:     List of Spotify track dicts with 'name' and 'artists' keys.
        max_tracks: Cap on how many tracks to process (avoid long waits).

    Returns:
        {spotify_uri: {tag: weight}} for all processed tracks.
    """
    result: dict[str, dict[str, float]] = {}
    processed = 0

    for track in tracks:
        if processed >= max_tracks:
            break
        uri = track.get("uri", "")
        name = track.get("name", "")
        artists = track.get("artists", [])
        artist_name = artists[0].get("name", "") if artists else ""

        if not name or not artist_name or not uri:
            continue

        # Check name-based cache first (covers both ISRC and name lookups)
        cache = _load_cache()
        key = _cache_key(artist_name, name)
        if key in cache:
            result[uri] = cache[key]
            continue

        # Try ISRC lookup first — more reliable than fuzzy name matching
        isrc = (track.get("external_ids") or {}).get("isrc", "")
        if isrc:
            isrc_key = f"isrc|{isrc.upper()}"
            if isrc_key in cache:
                tags = cache[isrc_key]
            else:
                tags = recording_tags_by_isrc(isrc)
            if tags:
                # Cross-cache under name key too so future name lookups hit cache
                cache = _load_cache()
                cache[key] = tags
                _save_cache()
                result[uri] = tags
                processed += 1
                continue

        # Fall back to name/title search
        tags = recording_tags(artist_name, name)
        result[uri] = tags
        processed += 1

    return result
