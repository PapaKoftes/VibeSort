"""
acoustid.py — AcoustID audio fingerprinting for local music files.

AcoustID identifies audio files by their acoustic fingerprint regardless of
filename, tags, or metadata. It returns a MusicBrainz Recording ID which
unlocks full MusicBrainz genre/tag data for tracks not in Spotify.

PRIMARY USE CASE
================
Users with local music files that don't have Spotify matches. Fingerprinting
lets us identify those tracks and feed them into the existing MusicBrainz /
Last.fm enrichment pipeline.

HOW IT WORKS
============
1. Run `fpcalc` (Chromaprint CLI) on an audio file → get fingerprint + duration
2. POST fingerprint to AcoustID API → get MusicBrainz Recording IDs
3. Use MBID to query MusicBrainz for genre tags
4. Merge into existing artist_genres_map / track_tags

REQUIREMENTS
============
  - `fpcalc` binary (ships with Chromaprint, available at acoustid.org/chromaprint)
    Must be on PATH or set FPCALC_PATH in .env
  - Free AcoustID API key at acoustid.org/login
  - Audio files (MP3, FLAC, OGG, etc.) accessible on disk

CONFIG (.env or Settings → Enrichment Sources)
===============================================
  ACOUSTID_API_KEY=your_key   # free at acoustid.org/login
  FPCALC_PATH=/path/to/fpcalc # optional, defaults to fpcalc on PATH
  LOCAL_MUSIC_PATH=/path/to/music  # root folder of local music files

RATE LIMIT
==========
AcoustID: 3 requests/second (enforced). Cached to disk forever.

CACHE
=====
outputs/.acoustid_cache.json — fingerprint→MBID mapping, permanent.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

_ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH  = os.path.join(_ROOT, "outputs", ".acoustid_cache.json")

_ACOUSTID_URL = "https://api.acoustid.org/v2/lookup"
_RATE_DELAY   = 0.35   # ~3 req/s
_AUDIO_EXTS   = {".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wav", ".wv"}

_cache: dict | None = None


# ── Cache ─────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    try:
        from core.cache_io import atomic_write_json
        atomic_write_json(CACHE_PATH, _cache)
    except OSError:
        pass


# ── fpcalc ────────────────────────────────────────────────────────────────────

def _find_fpcalc() -> str | None:
    """Return path to fpcalc binary or None if not found."""
    env_path = os.getenv("FPCALC_PATH", "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path
    # Check PATH
    import shutil
    return shutil.which("fpcalc")


def fingerprint_file(file_path: str) -> tuple[str, int] | None:
    """
    Run fpcalc on an audio file.

    Returns (fingerprint_string, duration_seconds) or None if fpcalc fails.
    """
    fpcalc = _find_fpcalc()
    if not fpcalc:
        return None
    try:
        result = subprocess.run(
            [fpcalc, "-json", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        fp   = data.get("fingerprint", "")
        dur  = int(data.get("duration", 0))
        return (fp, dur) if fp and dur > 0 else None
    except (subprocess.TimeoutExpired, subprocess.SubprocessError,
            json.JSONDecodeError, OSError):
        return None


# ── AcoustID API ──────────────────────────────────────────────────────────────

def lookup_fingerprint(
    api_key: str,
    fingerprint: str,
    duration: int,
) -> list[dict]:
    """
    Look up a fingerprint against the AcoustID database.

    Returns list of {"id": str, "score": float, "recordings": [{"id": mbid, ...}]}.
    """
    cache = _load_cache()
    cache_key = fingerprint[:40]  # first 40 chars sufficient for cache key
    if cache_key in cache:
        return cache[cache_key]

    time.sleep(_RATE_DELAY)
    params = urllib.parse.urlencode({
        "client":      api_key,
        "fingerprint": fingerprint,
        "duration":    duration,
        "meta":        "recordings releasegroups",
        "format":      "json",
    })
    url = f"{_ACOUSTID_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results", [])
        cache[cache_key] = results
        _save_cache()
        return results
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return []


def mbids_from_fingerprint(
    api_key: str,
    fingerprint: str,
    duration: int,
    min_score: float = 0.85,
) -> list[str]:
    """Return MusicBrainz Recording IDs for a fingerprint above min_score."""
    results = lookup_fingerprint(api_key, fingerprint, duration)
    mbids: list[str] = []
    for r in results:
        if r.get("score", 0) >= min_score:
            for rec in r.get("recordings", []):
                mbid = rec.get("id")
                if mbid and mbid not in mbids:
                    mbids.append(mbid)
    return mbids


# ── Directory scanner ─────────────────────────────────────────────────────────

def scan_directory(
    music_dir: str,
    api_key: str,
    max_files: int = 200,
    progress_fn=None,
) -> dict[str, list[str]]:
    """
    Fingerprint audio files in music_dir and return {file_path: [mbid, ...]}.

    Only processes files not already in cache.
    Uses the AcoustID API to resolve fingerprints to MusicBrainz Recording IDs.
    """
    if not os.path.isdir(music_dir):
        return {}

    results: dict[str, list[str]] = {}
    fpcalc = _find_fpcalc()
    if not fpcalc:
        return {}

    processed = 0
    for dirpath, _, filenames in os.walk(music_dir):
        for fname in filenames:
            if processed >= max_files:
                break
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _AUDIO_EXTS:
                continue
            fpath = os.path.join(dirpath, fname)
            fp_result = fingerprint_file(fpath)
            if not fp_result:
                continue
            fingerprint, duration = fp_result
            mbids = mbids_from_fingerprint(api_key, fingerprint, duration)
            if mbids:
                results[fpath] = mbids
            processed += 1
            if progress_fn and processed % 10 == 0:
                progress_fn(f"AcoustID: fingerprinted {processed} files...")

    return results


# ── Availability check ────────────────────────────────────────────────────────

def is_available() -> bool:
    """Return True if fpcalc is on PATH and usable."""
    return _find_fpcalc() is not None


def cache_stats() -> dict:
    cache = _load_cache()
    return {"fingerprints_cached": len(cache)}
