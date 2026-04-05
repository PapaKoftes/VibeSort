"""Import / wiring smoke tests (no network)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_import_core_modules():
    import core.audio_proxy  # noqa: F401
    import core.profile  # noqa: F401
    import core.scorer  # noqa: F401
    import core.scan_pipeline  # noqa: F401
    import config  # noqa: F401


def test_profile_build_roundtrip():
    from core.profile import build

    track = {
        "uri": "spotify:track:x",
        "name": "N",
        "artists": [{"id": "aid", "name": "A"}],
        "album": {"release_date": "2020-01-01"},
        "popularity": 40,
    }
    ag = {"aid": ["indie rock"]}
    af = {
        "spotify:track:x": {
            "energy": 0.6,
            "valence": 0.5,
            "danceability": 0.5,
            "tempo": 120,
            "acousticness": 0.3,
            "instrumentalness": 0.0,
            "_source": "metadata_proxy",
            "_proxy_confidence": 0.5,
        },
    }
    tt = {"spotify:track:x": {"chill": 0.5}}
    p = build(track, ag, af, tt)
    assert p["audio_vector_source"] == "metadata_proxy"
    assert len(p["audio_vector"]) == 6


def test_effective_genre_cross_genre_rescue():
    from core.scorer import effective_genre_score, genre_score
    from core.mood_graph import mood_preferred_genres

    pref = mood_preferred_genres("Hollow")
    metal = {"macro_genres": ["Metal"], "audio_vector": [0.5] * 6}
    assert genre_score(metal, pref) == 0.0
    rescue = effective_genre_score(metal, "Hollow", tag_s=0.2, sem_s=0.42)
    assert 0.2 < rescue <= 0.52

    indie = {"macro_genres": ["Indie / Alternative"], "audio_vector": [0.5] * 6}
    assert effective_genre_score(indie, "Hollow", 0.0, 0.0) == 1.0


def test_anchor_mood_key_normalises_slash():
    from core.anchors import get_anchor_ids, _normalise_mood_key

    assert _normalise_mood_key("Goth / Darkwave") == "goth_darkwave"
    assert isinstance(get_anchor_ids("Lo-Fi Flow"), list)
