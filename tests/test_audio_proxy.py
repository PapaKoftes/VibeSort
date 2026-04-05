"""Golden-style tests for metadata audio proxy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import audio_proxy


def test_proxy_trap_tags_tempo_band():
    track = {"uri": "spotify:track:1", "artists": [{"id": "a1", "name": "X"}]}
    genres = {"a1": ["hip hop"]}
    tags = {"spotify:track:1": {"trap": 0.8, "dark": 0.5}}
    d = audio_proxy.build_proxy_feature_dict(track, genres, tags)
    assert d is not None
    assert d["_source"] == "metadata_proxy"
    assert d["_proxy_tempo_band"] == "Cruise"
    assert 85 <= d["tempo"] <= 120


def test_proxy_no_signal_returns_none():
    track = {"uri": "spotify:track:2", "artists": [{"id": "b2", "name": "Y"}]}
    genres = {"b2": []}
    tags: dict = {}
    assert audio_proxy.build_proxy_feature_dict(track, genres, tags) is None


def test_proxy_shoegaze_macro_or_style():
    track = {"uri": "spotify:track:3", "artists": [{"id": "c3", "name": "Z"}]}
    genres = {"c3": ["shoegaze"]}
    tags = {"spotify:track:3": {}}
    d = audio_proxy.build_proxy_feature_dict(track, genres, tags)
    assert d is not None
    assert d["_proxy_tempo_band"] == "Slow Burn"


def test_merge_skips_real_spotify_shape():
    tracks = [{"uri": "u1", "artists": [{"id": "a", "name": "A"}]}]
    genres = {"a": ["rock"]}
    tags = {"u1": {"hype": 1.0}}
    audio_map = {"u1": {"energy": 0.7, "valence": 0.5, "tempo": 120.0}}
    n = audio_proxy.merge_proxy_into_audio_map(tracks, genres, tags, audio_map)
    assert n == 0
    assert audio_map["u1"].get("_source") != "metadata_proxy"


def test_merge_fills_empty():
    tracks = [{"uri": "u2", "artists": [{"id": "b", "name": "B"}]}]
    genres = {"b": ["metal"]}
    tags = {"u2": {"thrash": 0.9}}
    audio_map: dict = {}
    n = audio_proxy.merge_proxy_into_audio_map(tracks, genres, tags, audio_map)
    assert n == 1
    assert audio_map["u2"]["_source"] == "metadata_proxy"
