"""Tests for Spotify 429 retry helper."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import spotipy

from core.spotify_retry import call_with_429_backoff


def test_429_backoff_then_success():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise spotipy.SpotifyException(
                429,
                -1,
                "rate limited",
                headers={"Retry-After": "0"},
            )
        return "ok"

    assert call_with_429_backoff(fn, max_attempts=4) == "ok"
    assert calls["n"] == 2


def test_non_429_raises_immediately():
    def fn():
        raise spotipy.SpotifyException(404, -1, "not found")

    with pytest.raises(spotipy.SpotifyException) as ei:
        call_with_429_backoff(fn, max_attempts=4)
    assert ei.value.http_status == 404
