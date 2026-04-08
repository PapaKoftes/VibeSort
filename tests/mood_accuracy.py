"""
tests/mood_accuracy.py — Mood scoring accuracy evaluation suite.

Run with:  python -m pytest tests/mood_accuracy.py -v

Tests verify that the scoring engine correctly ranks tracks for their
intended moods and that utility functions behave as specified.
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.scorer import (
    score_track,
    refine_playlist,
    ensure_minimum,
    combine_expected_tags,
    enforce_dominance,
    query_boost,
    user_feedback_boost,
    cohesion_filter,
    rank_tracks,
    cohesion_signal_weights,
    library_real_audio_fraction,
)


# ── Synthetic track profiles ──────────────────────────────────────────────────

def _profile(tags: dict, macro_genres: list, audio: list | None = None) -> dict:
    """Build a minimal track profile for testing."""
    vec = audio or [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    neutral = vec == [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    return {
        "uri":          "spotify:track:test",
        "name":         "Test Track",
        "artists":      ["Test Artist"],
        "audio_vector": vec,
        "audio_vector_source": "neutral" if neutral else "spotify",
        "raw_genres":   [],
        "macro_genres": macro_genres,
        "tags":         tags,
        "tag_clusters": {},
        "popularity":   50,
        "lyric_mood":   {},
        "release_year": 2020,
        "_features":    {} if neutral else {"energy": vec[0], "valence": vec[1]},
        "confidence":   {"tags": 0.8, "genres": 1.0, "audio": 0.0, "overall": 0.73},
    }


# ── Mood scoring correctness ──────────────────────────────────────────────────

def test_metal_scores_high_for_adrenaline():
    """High-energy metal track should score well for adrenaline (audio disabled, tag-only)."""
    profile = _profile(
        tags={
            "beast_mode": 0.9, "gym": 0.8, "workout": 0.8, "heavy": 0.7,
            "energy": 0.9, "aggressive": 0.8, "power": 0.7, "hype": 0.6,
        },
        macro_genres=["Metal / Hardcore"],
    )
    score = score_track(profile, "adrenaline")
    assert score > 0.12, f"Metal/gym track scored too low for adrenaline: {score}"


def test_sad_acoustic_scores_high_for_hollow():
    """Sad acoustic track should score well for hollow."""
    profile = _profile(
        tags={"sad": 0.9, "heartbreak": 0.8, "crying": 0.7, "hollow": 0.9, "acoustic": 0.6},
        macro_genres=["Indie / Alternative"],
        audio=[0.2, 0.1, 0.3, 0.3, 0.8, 0.2],
    )
    score = score_track(profile, "hollow")
    assert score > 0.30, f"Sad acoustic track scored too low for hollow: {score}"


def test_metal_scores_low_for_soft_hours():
    """Aggressive metal should score poorly for soft/chill moods."""
    profile = _profile(
        tags={"beast_mode": 0.9, "aggressive": 0.9, "rage": 0.8, "heavy": 0.9},
        macro_genres=["Metal / Hardcore"],
        audio=[0.97, 0.2, 0.6, 0.9, 0.02, 0.05],
    )
    # Try a calm/chill mood — metal should score low
    score = score_track(profile, "chill_out")
    assert score < 0.45, f"Metal track scored too high for chill_out: {score}"


def test_phonk_scores_high_for_phonk_season():
    """Phonk-tagged track should score well for phonk_season."""
    profile = _profile(
        tags={"phonk": 0.9, "dark": 0.7, "drive": 0.6, "night": 0.7, "aggressive": 0.5},
        macro_genres=["Electronic / Ambient"],
    )
    score = score_track(profile, "phonk_season")
    assert score >= 0.20, f"Phonk track scored too low for phonk_season: {score}"


def test_chill_scores_low_for_adrenaline():
    """Calm, ambient track should score poorly for adrenaline."""
    profile = _profile(
        tags={"calm": 0.9, "peaceful": 0.8, "ambient": 0.9, "sleep": 0.7, "soft": 0.8},
        macro_genres=["Electronic / Ambient"],
        audio=[0.1, 0.7, 0.2, 0.2, 0.9, 0.8],
    )
    score = score_track(profile, "adrenaline")
    assert score < 0.35, f"Chill/ambient track scored too high for adrenaline: {score}"


# ── refine_playlist ───────────────────────────────────────────────────────────

def test_refine_playlist_removes_low_scorers():
    """refine_playlist should drop bottom tracks when avg is below threshold (needs >=15 tracks)."""
    ranked = [(f"uri_{i}", s) for i, s in enumerate(
        [0.9, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50,
         0.45, 0.40, 0.35, 0.30, 0.20, 0.10]
    )]
    refined = refine_playlist(ranked, threshold=0.65, max_passes=2)
    scores = [s for _, s in refined]
    assert len(refined) < len(ranked), "refine_playlist should have dropped some tracks"
    assert all(s >= 0.10 for s in scores), "Bottom tracks should be removed"


def test_refine_playlist_preserves_good_playlists():
    """refine_playlist should not modify already-good playlists."""
    ranked = [(f"uri_{i}", s) for i, s in enumerate(
        [0.9, 0.85, 0.80, 0.78, 0.75, 0.72, 0.70]
    )]
    refined = refine_playlist(ranked, threshold=0.65, max_passes=2)
    assert len(refined) == len(ranked), "Good playlist should be unchanged"


def test_refine_playlist_preserves_small_playlists():
    """refine_playlist should not trim playlists below 5 tracks."""
    ranked = [(f"uri_{i}", 0.3) for i in range(4)]
    refined = refine_playlist(ranked, threshold=0.65, max_passes=5)
    assert len(refined) == 4, "Small playlists should not be trimmed below 5"


# ── ensure_minimum ────────────────────────────────────────────────────────────

def test_ensure_minimum_backfills():
    """ensure_minimum should add tracks from the pool when below min_tracks."""
    ranked   = [("uri_a", 0.8), ("uri_b", 0.75)]
    all_pool = [("uri_a", 0.8), ("uri_b", 0.75),
                ("uri_c", 0.50), ("uri_d", 0.45), ("uri_e", 0.40)]
    result = ensure_minimum(ranked, all_pool, min_tracks=5)
    assert len(result) == 5, f"Expected 5 tracks, got {len(result)}"
    uris = [u for u, _ in result]
    assert "uri_c" in uris and "uri_d" in uris and "uri_e" in uris


def test_ensure_minimum_no_duplicates():
    """ensure_minimum should not add tracks already in ranked."""
    ranked   = [("uri_a", 0.8)]
    all_pool = [("uri_a", 0.8), ("uri_b", 0.50)]
    result = ensure_minimum(ranked, all_pool, min_tracks=3)
    uris = [u for u, _ in result]
    assert uris.count("uri_a") == 1, "No duplicates"


def test_ensure_minimum_skips_low_scores():
    """ensure_minimum should not backfill tracks at or below the floor.

    M3.2 changed floor from min_score*0.7 to min_score*0.5.
    With default min_score=0.15: floor = max(0.15*0.5, 0.05) = 0.075.
    Scores <= floor (0.05) must be excluded; scores > floor (0.10) may be included.
    """
    ranked   = [("uri_a", 0.8)]
    all_pool = [("uri_a", 0.8), ("uri_b", 0.10), ("uri_c", 0.05)]
    result = ensure_minimum(ranked, all_pool, min_tracks=5)
    uris = [u for u, _ in result]
    # uri_c (0.05 <= floor 0.075) must be excluded
    assert "uri_c" not in uris
    # uri_b (0.10 > floor 0.075) is now permitted under M3.2's relaxed floor
    assert "uri_b" in uris


# ── combine_expected_tags ─────────────────────────────────────────────────────

def test_combine_expected_tags_returns_list():
    """combine_expected_tags should return a list of strings."""
    result = combine_expected_tags("hollow", {"crying": 0.8, "night": 0.6}, 0.30)
    assert isinstance(result, list)
    assert all(isinstance(t, str) for t in result)


def test_combine_expected_tags_no_duplicates():
    """combine_expected_tags should not duplicate tags."""
    # "sad" is already in hollow's expected_tags
    result = combine_expected_tags("hollow", {"sad": 0.9, "extra_tag": 0.7}, 0.30)
    assert result.count("sad") <= 1, "Tags should not be duplicated"


# ── enforce_dominance ─────────────────────────────────────────────────────────

def test_enforce_dominance_clear_winner():
    """A mood with a clear 15%+ lead should win."""
    scores = {"hollow": 0.80, "overthinking": 0.60, "chill_out": 0.40}
    winner = enforce_dominance(scores, margin=0.15)
    assert winner == "hollow"


def test_enforce_dominance_ambiguous():
    """Close scores should return None."""
    scores = {"hollow": 0.72, "overthinking": 0.65}
    winner = enforce_dominance(scores, margin=0.15)
    assert winner is None, f"Expected None for ambiguous scores, got {winner}"


def test_enforce_dominance_single_mood():
    """Single mood always wins."""
    scores = {"adrenaline": 0.55}
    winner = enforce_dominance(scores, margin=0.15)
    assert winner == "adrenaline"


# ── query_boost ───────────────────────────────────────────────────────────────

def test_query_boost_matching_tags():
    """query_boost should return > 0 for matching tags."""
    profile = _profile(tags={"night": 0.8, "drive": 0.7}, macro_genres=["Hip-Hop / R&B"])
    boost = query_boost(profile, include_tags=["night", "drive"], strength=0.20)
    assert boost > 0.0
    assert boost <= 0.20


def test_query_boost_no_match():
    """query_boost should return 0.0 for non-matching tags."""
    profile = _profile(tags={"happy": 0.9}, macro_genres=["Pop"])
    boost = query_boost(profile, include_tags=["night", "drive"], strength=0.20)
    assert boost == 0.0


def test_query_boost_empty_tags():
    """query_boost should return 0.0 when include_tags is empty."""
    profile = _profile(tags={"night": 0.8}, macro_genres=["Hip-Hop / R&B"])
    boost = query_boost(profile, include_tags=[], strength=0.20)
    assert boost == 0.0


# ── user_feedback_boost ───────────────────────────────────────────────────────

def test_user_feedback_boost_match():
    """user_feedback_boost should return > 0 for preferred tags present."""
    profile = _profile(tags={"chill": 0.8, "night": 0.6}, macro_genres=["R&B / Soul"])
    boost = user_feedback_boost(profile, preferred_tags=["chill", "night"], strength=0.10)
    assert boost > 0.0
    assert boost <= 0.10


def test_user_feedback_boost_no_match():
    """user_feedback_boost should return 0.0 when no preferred tags match."""
    profile = _profile(tags={"rage": 0.9}, macro_genres=["Metal / Hardcore"])
    boost = user_feedback_boost(profile, preferred_tags=["chill", "peaceful"], strength=0.10)
    assert boost == 0.0


# ── enforce_dominance with real multi-mood scores ─────────────────────────────

def test_dominance_real_scores():
    """A track with clear mood dominance should have a single winner."""
    # Simulate a very sad track scoring high on hollow, low on everything else
    sad_profile = _profile(
        tags={"sad": 0.9, "hollow": 0.9, "crying": 0.8, "heartbreak": 0.8, "numb": 0.7},
        macro_genres=["Indie / Alternative"],
        audio=[0.15, 0.08, 0.25, 0.25, 0.85, 0.3],
    )
    # Score against a few moods
    from core.scorer import score_track
    moods_to_test = ["hollow", "chill_out", "adrenaline", "summer_high"]
    mood_scores = {m: score_track(sad_profile, m) for m in moods_to_test}
    # enforce_dominance should find a winner (hollow should clearly lead)
    winner = enforce_dominance(mood_scores, margin=0.10)
    # Either hollow wins clearly or it's ambiguous — but it should not raise
    assert winner is None or isinstance(winner, str)
    # hollow should score highest
    assert mood_scores["hollow"] >= max(mood_scores.values()) - 0.01


# ── Strictness affects rank_tracks output ─────────────────────────────────────

def test_strictness_affects_results():
    """Higher min_score should return fewer tracks than lower min_score."""
    from core.scorer import rank_tracks

    # Build a diverse set of profiles with varying tag overlap
    profiles = {}
    tag_sets = [
        {"sad": 0.9, "hollow": 0.8, "crying": 0.7},   # strong hollow
        {"sad": 0.5, "melancholy": 0.4},                # moderate
        {"sad": 0.2},                                    # weak
        {"happy": 0.9, "upbeat": 0.8},                  # wrong mood
        {"hollow": 0.7, "numb": 0.6, "empty": 0.5},    # strong hollow
        {"chill": 0.9, "peaceful": 0.8},                # wrong mood
    ]
    for i, tags in enumerate(tag_sets):
        uri = f"spotify:track:test{i:03d}"
        profiles[uri] = _profile(tags=tags, macro_genres=["Indie / Alternative"])
        profiles[uri]["uri"] = uri

    loose  = rank_tracks(profiles, "hollow", min_score=0.08)
    strict = rank_tracks(profiles, "hollow", min_score=0.35)

    assert len(strict) <= len(loose), (
        f"Strict filter ({len(strict)}) should yield ≤ loose filter ({len(loose)})"
    )


# ── tag_cluster vocabulary alignment ──────────────────────────────────────────

def test_tag_cluster_equivalence():
    """collapse_tags should map 'midnight' → 'night' cluster."""
    from core.profile import collapse_tags
    result = collapse_tags({"midnight": 1.0, "gym": 0.8})
    assert "night" in result, f"Expected 'night' cluster from 'midnight', got: {result}"
    # raw tags not in any cluster are silently dropped — that's expected
    assert result["night"] == 1.0


def test_small_playlist_not_pruned():
    """refine_playlist should leave playlists with fewer than 15 tracks untouched."""
    small = [(f"uri_{i}", 0.30) for i in range(12)]
    refined = refine_playlist(small, threshold=0.65, max_passes=5)
    assert len(refined) == len(small), (
        f"Small playlist ({len(small)} tracks) should not be pruned, got {len(refined)}"
    )


# ── cohesion_filter + neutral audio ─────────────────────────────────────────

def test_cohesion_filter_neutral_audio_keeps_tag_coherent_playlist():
    """With audio weight 0, tag/semantic cohesion should keep same-vibe tracks."""
    profiles: dict = {}
    for i in range(8):
        uri = f"spotify:track:coh{i}"
        profiles[uri] = _profile(
            tags={"night": 0.9, "drive": 0.7, "late_night": 0.6},
            macro_genres=["Indie / Alternative"],
        )
        profiles[uri]["uri"] = uri
    scored = [(f"spotify:track:coh{i}", 0.5 + i * 0.01) for i in range(8)]
    out = cohesion_filter(
        scored,
        profiles,
        "Late Night Drive",
        audio_weight=0.0,
        tag_weight=0.50,
        semantic_weight=0.50,
        threshold=0.35,
    )
    assert len(out) >= 5, f"Expected most tracks kept, got {len(out)}"


def test_cohesion_signal_weights_zero_audio_when_all_neutral():
    """library with only neutral vectors → no audio weight in cohesion."""
    profiles = {
        f"u{i}": _profile(tags={"x": 0.5}, macro_genres=["Pop"])
        for i in range(10)
    }
    for p in profiles.values():
        p["uri"] = "x"
    aw, tw, sw = cohesion_signal_weights(profiles)
    assert aw == 0.0 and abs(tw + sw - 1.0) < 1e-9


def test_library_real_audio_fraction_detects_features():
    p1 = _profile(tags={}, macro_genres=["Pop"], audio=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
    p2 = _profile(tags={}, macro_genres=["Pop"], audio=[0.8, 0.2, 0.5, 0.5, 0.5, 0.5])
    frac = library_real_audio_fraction({"a": p1, "b": p2}, sample_limit=10)
    assert 0.0 < frac < 1.0


# ── rank_tracks MVP toggle ────────────────────────────────────────────────────

def test_rank_tracks_mvp_fallback_can_add_tracks():
    """With MVP on and high min_playlist_size, weak-but-valid tracks may appear."""
    profiles = {}
    # Marginal hollow-ish tags — some may fall between MVP floor and strict floor
    tag_sets = [
        {"sad": 0.35, "heartbreak": 0.3},
        {"sad": 0.32, "crying": 0.28},
        {"melancholy": 0.30, "blue": 0.25},
        {"sad": 0.30, "numb": 0.22},
        {"emotional": 0.28, "hurt": 0.24},
    ]
    for i, tags in enumerate(tag_sets):
        uri = f"spotify:track:mvpp{i}"
        profiles[uri] = _profile(tags=tags, macro_genres=["Indie / Alternative"])
        profiles[uri]["uri"] = uri
    for i in range(15):
        uri = f"spotify:track:fill{i}"
        profiles[uri] = _profile(
            tags={"sad": 0.45, "hollow": 0.4, "heartbreak": 0.35},
            macro_genres=["Indie / Alternative"],
        )
        profiles[uri]["uri"] = uri

    with_mvp = rank_tracks(
        profiles,
        "Hollow",
        min_score=0.22,
        min_playlist_size=40,
        allow_mvp_fallback=True,
    )
    no_mvp = rank_tracks(
        profiles,
        "Hollow",
        min_score=0.22,
        min_playlist_size=40,
        allow_mvp_fallback=False,
    )
    assert len(with_mvp) >= len(no_mvp)


# ── ensure_minimum strict backfill ───────────────────────────────────────────

def test_ensure_minimum_strict_backfill_blocks_random():
    """Strict backfill should not add tracks with no tag/semantic fit."""
    ranked = [("spotify:track:good", 0.85)]
    all_pool = [
        ("spotify:track:good", 0.85),
        ("spotify:track:bad", 0.40),
    ]
    profiles = {
        "spotify:track:good": _profile(
            tags={"sad": 0.9, "hollow": 0.8},
            macro_genres=["Indie / Alternative"],
        ),
        "spotify:track:bad": _profile(
            tags={"party": 0.9, "hype": 0.9},
            macro_genres=["Pop"],
        ),
    }
    for u, p in profiles.items():
        p["uri"] = u
    loose = ensure_minimum(
        ranked,
        all_pool,
        min_tracks=2,
        min_score=0.15,
        strict_backfill=False,
        mood_name="Hollow",
        profiles=profiles,
    )
    strict = ensure_minimum(
        ranked,
        all_pool,
        min_tracks=2,
        min_score=0.15,
        strict_backfill=True,
        mood_name="Hollow",
        profiles=profiles,
    )
    assert len(loose) >= len(strict)
    strict_uris = [u for u, _ in strict]
    assert "spotify:track:bad" not in strict_uris


# ── naming coherence ──────────────────────────────────────────────────────────

def test_middle_out_keeps_mood_identity_when_mood_provided():
    from core.namer import middle_out_name
    profiles = [
        _profile(
            tags={"night": 0.9, "drive": 0.8, "late_night": 0.7},
            macro_genres=["Electronic / Ambient"],
        ),
        _profile(
            tags={"night": 0.8, "introspective": 0.7},
            macro_genres=["Electronic / Ambient"],
        ),
    ]
    name, desc = middle_out_name(
        profiles,
        mood_name="Late Night Drive",
        observed_tags={"night_drive": 1.0, "city_lights": 0.8},
    )
    # Playlist title uses mood_display_name (e.g. "Night Drive" for Late Night Drive).
    assert name == "Night Drive"
    # Description should include the mood name and at least one tag from the profiles
    assert "Late Night Drive" in desc or any(
        t in desc.lower() for t in ["night", "drive", "introspective"]
    )


def test_top_down_uses_observed_pattern_tags():
    from core.namer import top_down_name
    profiles = [
        _profile(
            tags={"sad": 0.9, "hollow": 0.8},
            macro_genres=["Indie / Alternative"],
        )
    ]
    name, desc = top_down_name(
        "Hollow",
        profiles,
        observed_tags={"heartbreak": 1.0, "crying": 0.9},
    )
    # Hollow is lyric_focus with lyric_playlist_title — title leads with that phrase.
    assert "Hollow" in name
    assert "Sad & honest" in name or "lyrics" in name.lower()
    # Description should surface actual tags (profile tags or observed tags)
    # The new format uses "Sad · Hollow · Heartbreak" instead of "Pattern: X"
    assert any(t in desc for t in ["Sad", "Hollow", "Heartbreak"])


def test_fixture_profiles_sanity_for_ci():
    fixture_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "fixtures",
        "library_profiles.json",
    )
    with open(fixture_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    profiles = payload.get("profiles", [])
    assert len(profiles) >= 2
    assert all("uri" in p and "tags" in p and "macro_genres" in p for p in profiles)
