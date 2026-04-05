"""
spotify_retry.py — Retry Spotify Web API calls on HTTP 429 (rate limit).

Uses Retry-After when present; otherwise exponential-style backoff.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

import spotipy

T = TypeVar("T")


def _retry_after_seconds(exc: spotipy.SpotifyException) -> float | None:
    h = getattr(exc, "headers", None) or {}
    if not isinstance(h, dict):
        try:
            h = dict(h)
        except (TypeError, ValueError):
            h = {}
    raw = h.get("Retry-After") or h.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def call_with_429_backoff(fn: Callable[[], T], *, max_attempts: int = 4) -> T:
    """
    Run ``fn`` and retry on HTTP 429 up to ``max_attempts`` times.
    Re-raises the last SpotifyException if non-429 or retries exhausted.
    """
    last: spotipy.SpotifyException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except spotipy.SpotifyException as e:
            last = e
            if getattr(e, "http_status", None) != 429 or attempt >= max_attempts - 1:
                raise
            ra = _retry_after_seconds(e)
            time.sleep(ra if ra is not None else (1.5 + attempt * 2.0))
    assert last is not None
    raise last
