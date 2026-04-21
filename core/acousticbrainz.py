"""
core/acousticbrainz.py — Local audio analysis via librosa.

AcousticBrainz (acousticbrainz.org) was shut down by the MetaBrainz Foundation
in December 2022 and is no longer available.  Spotify's audio-features endpoint
was deprecated in November 2024.

This module handles LOCAL FILE analysis only — it uses librosa to extract
acoustic features from audio files on disk.  It is activated when the user
sets LOCAL_MUSIC_PATH in config / .env and librosa is installed.

For Spotify tracks the scoring pipeline uses the metadata proxy (audio_proxy.py)
which derives energy, valence, danceability, tempo, acousticness, and
instrumentalness from Deezer BPM/gain, genre heuristics, and lyric sentiment.

Usage
-----
    from core.acousticbrainz import analyse_local, is_available

    if is_available():
        features = analyse_local("/path/to/track.mp3")
        # → {"bpm": 128.0, "energy": 0.72, "spectral_centroid": 2400.0,
        #    "zcr": 0.08, "duration_s": 213.4, "source": "librosa"}

Integration
-----------
scan_pipeline.py falls back to this module for spotify:local: URIs when
librosa is installed and LOCAL_MUSIC_PATH points to the local music folder.

The returned feature dict uses the same axis names as audio_proxy.py where
possible so the scoring engine treats both sources identically:
  bpm            → maps to "tempo" in profile.py
  energy         → 0–1 RMS-normalised, same axis as proxy energy
  spectral_centroid → brightness heuristic (no proxy equivalent)
  zcr            → zero-crossing rate; proxy for noisiness / distortion
"""

from __future__ import annotations

import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Cache: path → feature dict, avoids re-analysing the same file in one session
_analysis_cache: dict[str, dict[str, Any]] = {}


def is_available() -> bool:
    """Return True if librosa is installed and usable."""
    try:
        import librosa  # noqa: F401
        return True
    except ImportError:
        return False


def analyse_local(file_path: str, *, sr: int = 22050) -> dict[str, Any] | None:
    """
    Analyse a local audio file and return acoustic features.

    Parameters
    ----------
    file_path : str
        Absolute path to an audio file (mp3, flac, ogg, wav, m4a, …).
    sr : int
        Sample rate to use for analysis.  22 050 Hz is the librosa default
        and a good balance of speed vs accuracy.

    Returns
    -------
    dict with keys:
        bpm               (float)  — estimated tempo in beats per minute
        energy            (float)  — RMS energy normalised to 0–1
        spectral_centroid (float)  — mean spectral centroid in Hz (brightness)
        zcr               (float)  — mean zero-crossing rate
        duration_s        (float)  — track duration in seconds
        source            (str)    — always "librosa"
    None if analysis fails (file not found, librosa not installed, decode error).
    """
    if file_path in _analysis_cache:
        return _analysis_cache[file_path]

    if not os.path.isfile(file_path):
        logger.debug("acousticbrainz: file not found: %s", file_path)
        return None

    try:
        import librosa
        import numpy as np
    except ImportError:
        logger.debug("acousticbrainz: librosa not installed — local analysis unavailable")
        return None

    try:
        y, _sr = librosa.load(file_path, sr=sr, mono=True)

        tempo, _ = librosa.beat.beat_track(y=y, sr=_sr)
        bpm = float(np.atleast_1d(tempo)[0])

        rms = librosa.feature.rms(y=y)[0]
        energy_raw = float(np.mean(rms))
        # Normalise: typical music peaks around 0.15–0.25 RMS; clamp to [0, 1]
        energy = min(energy_raw / 0.20, 1.0)

        sc = librosa.feature.spectral_centroid(y=y, sr=_sr)[0]
        spectral_centroid = float(np.mean(sc))

        zcr = librosa.feature.zero_crossing_rate(y)[0]
        zcr_mean = float(np.mean(zcr))

        duration_s = librosa.get_duration(y=y, sr=_sr)

        result: dict[str, Any] = {
            "bpm":               round(bpm, 2),
            "energy":            round(energy, 4),
            "spectral_centroid": round(spectral_centroid, 2),
            "zcr":               round(zcr_mean, 6),
            "duration_s":        round(duration_s, 2),
            "source":            "librosa",
        }
        _analysis_cache[file_path] = result
        return result

    except Exception as exc:
        logger.warning("acousticbrainz: failed to analyse %s: %s", file_path, exc)
        return None


def analyse_batch(
    file_paths: list[str],
    *,
    sr: int = 22050,
    progress_cb=None,
) -> dict[str, dict[str, Any]]:
    """
    Analyse a list of local audio files.

    Parameters
    ----------
    file_paths : list[str]
        Paths to audio files.
    sr : int
        Sample rate for librosa.
    progress_cb : callable(done, total) | None
        Optional progress callback, called after each file completes.

    Returns
    -------
    dict mapping file_path → feature dict (skips files that failed).
    """
    results: dict[str, dict[str, Any]] = {}
    total = len(file_paths)
    for i, path in enumerate(file_paths, 1):
        feat = analyse_local(path, sr=sr)
        if feat is not None:
            results[path] = feat
        if progress_cb:
            try:
                progress_cb(i, total)
            except Exception:
                pass
    return results


def resolve_local_path(uri: str, local_music_path: str | None) -> str | None:
    """
    Attempt to resolve a spotify:local: URI to a file path under local_music_path.

    Spotify local URIs have the form:
        spotify:local:<artist>:<album>:<title>:<duration_ms>

    All components are URL-encoded.  We search for a matching filename
    under local_music_path by title (the most stable component).

    Returns the first matching file path, or None if no match found.
    """
    if not uri.startswith("spotify:local:") or not local_music_path:
        return None
    if not os.path.isdir(local_music_path):
        return None

    from urllib.parse import unquote

    parts = uri.split(":")
    # parts: ['spotify', 'local', artist, album, title, duration_ms]
    if len(parts) < 6:
        return None

    title = unquote(parts[4]).lower().strip()
    if not title:
        return None

    audio_extensions = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac", ".opus"}

    for root, _dirs, files in os.walk(local_music_path):
        for fname in files:
            stem, ext = os.path.splitext(fname)
            if ext.lower() in audio_extensions and title in stem.lower():
                return os.path.join(root, fname)

    return None
