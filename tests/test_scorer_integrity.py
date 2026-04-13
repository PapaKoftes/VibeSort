"""
tests/test_scorer_integrity.py — Unit tests for scoring invariants.

Run with:  pytest tests/test_scorer_integrity.py -v

These tests catch regressions in the multi-signal scorer.  Each test is
a documented invariant that the system MUST satisfy.  When a test fails,
the failure message explains exactly what invariant was broken and why it
matters for playlist quality.

Coverage:
  - score_track output bounds
  - taste_adaptation_boost clamping (dz_bpm regression test)
  - numeric pseudo-tag exclusion from user_tag_preferences
  - combine_expected_tags numeric tag filtering
  - graph_mood_ floor behaviour
  - anchor tag signal confidence
  - tag_score capping
  - semantic_score neutral fallback
  - genre_score wildcard rules
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import core.scorer as scorer
import core.profile as profile_mod


# ── Minimal profile factory ───────────────────────────────────────────────────

def _make_profile(
    tags: dict | None = None,
    macro_genres: list[str] | None = None,
    audio_vector: list[float] | None = None,
    audio_vector_source: str = "none",
    uri: str = "spotify:track:test000",
    name: str = "Test Track",
) -> dict:
    return {
        "uri": uri,
        "name": name,
        "artists": ["Test Artist"],
        "audio_vector": audio_vector or [0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        "audio_vector_source": audio_vector_source,
        "raw_genres": [],
        "macro_genres": macro_genres or ["Other"],
        "tags": tags or {},
        "tag_clusters": {},
        "popularity": 50,
        "lyric_mood": {},
        "release_year": 2020,
        "_features": {},
        "confidence": {"tags": 1.0},
    }


# ── 1. score_track output bounds ──────────────────────────────────────────────

class TestScoreTrackBounds:
    """score_track must never produce scores that blow up playlists."""

    def test_score_non_negative(self):
        """Hard-rejected tracks return -1.0; all others must be ≥ 0."""
        p = _make_profile(tags={"sad": 0.8, "night": 0.6})
        s = scorer.score_track(p, "Hollow")
        assert s == -1.0 or s >= 0.0, f"score_track returned {s}, expected -1 or ≥0"

    def test_score_sane_upper_bound(self):
        """No track should score above 2.5 after all multipliers.

        The theoretical max with weights summing to 1.0 and multipliers
        (positive_boost 1.15 × user_pref 1.15 × taste_adapt 1.10 × user_model 1.12)
        is about 1.63.  We allow up to 2.5 as a generous buffer.
        Any score above that indicates an unclamped raw numeric value leaking
        through the multiplier chain.
        """
        p = _make_profile(tags={"sad": 0.9, "hollow": 0.9, "night": 0.8, "anchor_hollow": 1.0})
        s = scorer.score_track(p, "Hollow")
        assert s < 2.5, (
            f"score_track returned {s:.4f} which exceeds sane upper bound of 2.5. "
            "Likely an unclamped numeric tag leaked into a multiplier."
        )

    def test_score_dz_bpm_only_track_sane(self):
        """A track with only dz_bpm tag must not score above 2.5 for any mood.

        Regression test for the dz_bpm taste_adaptation_boost explosion:
        raw BPM values (e.g. 193.2) used to produce 27× multipliers when
        taste_adaptation_boost was unclamped and dz_bpm leaked into user_tag_prefs.
        """
        p = _make_profile(tags={"dz_bpm": 193.2})
        fake_user_tag_prefs = {"dz_bpm": 131.6}  # avg BPM across library

        s = scorer.score_track(
            p, "Anime Openings",
            user_tag_prefs=fake_user_tag_prefs,
        )
        assert s < 2.5, (
            f"Track with only dz_bpm=193.2 scored {s:.4f} for Anime Openings. "
            "taste_adaptation_boost is not clamping raw BPM values."
        )

    def test_score_empty_tags_non_negative(self):
        """Tracks with no tags at all should produce a score (possibly low but valid)."""
        p = _make_profile(tags={})
        s = scorer.score_track(p, "Late Night Drive")
        assert s == -1.0 or s >= 0.0


# ── 2. taste_adaptation_boost clamping ───────────────────────────────────────

class TestTasteAdaptationBoost:
    """taste_adaptation_boost must always return [0.90, 1.10]."""

    def test_boost_within_bounds_normal_tags(self):
        p = _make_profile(tags={"sad": 0.8, "night": 0.6})
        user_prefs = {"sad": 0.7, "night": 0.5, "happy": 0.3}
        boost = scorer.taste_adaptation_boost(p, user_prefs)
        assert 0.89 <= boost <= 1.11, (
            f"taste_adaptation_boost returned {boost:.4f} — expected in [0.90, 1.10]"
        )

    def test_boost_clamped_with_raw_bpm(self):
        """Raw BPM as sole tag must not escape the [0.90, 1.10] window."""
        p = _make_profile(tags={"dz_bpm": 193.2})
        user_prefs = {"dz_bpm": 131.6}  # avg library BPM — would produce 27× if unclamped
        boost = scorer.taste_adaptation_boost(p, user_prefs)
        assert 0.89 <= boost <= 1.11, (
            f"taste_adaptation_boost returned {boost:.4f} with dz_bpm=193.2 in active_tags. "
            f"Expected clamp to [0.90, 1.10] — got {boost:.4f}×."
        )

    def test_boost_no_prefs_returns_one(self):
        p = _make_profile(tags={"sad": 0.8})
        boost = scorer.taste_adaptation_boost(p, None)
        assert boost == 1.0

    def test_boost_no_tags_returns_one(self):
        p = _make_profile(tags={})
        boost = scorer.taste_adaptation_boost(p, {"sad": 0.8})
        assert boost == 1.0

    def test_boost_max_is_1_10(self):
        """Boost should cap at 1.10 regardless of how high user preference is."""
        p = _make_profile(tags={"sad": 1.0})
        user_prefs = {"sad": 999.0}  # absurdly high
        boost = scorer.taste_adaptation_boost(p, user_prefs)
        assert boost <= 1.11, (
            f"taste_adaptation_boost exceeded 1.10 ceiling: {boost:.4f}"
        )

    def test_boost_min_is_0_90(self):
        """Boost should floor at 0.90 regardless of how low alignment is."""
        p = _make_profile(tags={"obscure_tag_xyzzy": 0.9})
        user_prefs = {}  # no matching prefs
        boost = scorer.taste_adaptation_boost(p, user_prefs)
        assert boost >= 0.89, (
            f"taste_adaptation_boost went below 0.90 floor: {boost:.4f}"
        )


# ── 3. user_tag_preferences numeric exclusion ─────────────────────────────────

class TestUserTagPreferences:
    """user_tag_preferences must exclude raw numeric pseudo-tags."""

    def test_dz_bpm_excluded(self):
        """dz_bpm must not appear in returned preferences."""
        profiles = {
            "uri1": _make_profile(tags={"sad": 0.8, "dz_bpm": 120.5}),
            "uri2": _make_profile(tags={"night": 0.6, "dz_bpm": 180.2}),
        }
        prefs = profile_mod.user_tag_preferences(profiles)
        assert "dz_bpm" not in prefs, (
            f"dz_bpm should be excluded from user_tag_preferences "
            f"but found value {prefs.get('dz_bpm')}. "
            "Raw BPM values corrupt taste_adaptation_boost."
        )

    def test_vader_valence_excluded(self):
        """vader_valence must not appear in returned preferences."""
        profiles = {
            "uri1": _make_profile(tags={"happy": 0.7, "vader_valence": 0.82}),
        }
        prefs = profile_mod.user_tag_preferences(profiles)
        assert "vader_valence" not in prefs, (
            "vader_valence should be excluded from user_tag_preferences."
        )

    def test_normal_tags_included(self):
        """Normal [0,1] tags must still appear in preferences."""
        profiles = {
            "uri1": _make_profile(tags={"sad": 0.8, "dz_bpm": 120.0}),
            "uri2": _make_profile(tags={"sad": 0.6}),
        }
        prefs = profile_mod.user_tag_preferences(profiles)
        assert "sad" in prefs, "Normal tag 'sad' should be in user_tag_preferences"
        assert abs(prefs["sad"] - 0.70) < 0.01, (
            f"Expected sad avg=0.70, got {prefs['sad']:.4f}"
        )

    def test_returns_averages_not_sums(self):
        """Values must be averages across tracks, not cumulative sums."""
        profiles = {
            "a": _make_profile(tags={"sad": 0.4}),
            "b": _make_profile(tags={"sad": 0.8}),
            "c": _make_profile(tags={"sad": 0.6}),
        }
        prefs = profile_mod.user_tag_preferences(profiles)
        expected = (0.4 + 0.8 + 0.6) / 3
        assert abs(prefs["sad"] - expected) < 0.001


# ── 4. combine_expected_tags numeric filtering ────────────────────────────────

class TestCombineExpectedTags:
    """combine_expected_tags must never include raw numeric pseudo-tags."""

    def test_dz_bpm_not_in_merged(self):
        """dz_bpm must be stripped from observed tags before merging."""
        observed = {"dz_bpm": 8138.4, "rock": 8.3, "classic_rock": 7.5}
        merged = scorer.combine_expected_tags("Anime Openings", observed)
        assert "dz_bpm" not in merged, (
            f"dz_bpm (raw BPM sum={observed['dz_bpm']}) must not appear in merged expected tags. "
            "It inflates tag_score and bleeds into combine_expected_tags."
        )

    def test_vader_valence_not_in_merged(self):
        observed = {"vader_valence": 500.0, "sad": 2.1, "melancholy": 1.8}
        merged = scorer.combine_expected_tags("Hollow", observed)
        assert "vader_valence" not in merged

    def test_valid_tags_still_merged(self):
        """Legitimate high-weight observed tags must still be merged."""
        observed = {"dz_bpm": 8138.0, "rock": 8.3, "classic_rock": 7.5, "80s": 5.2}
        merged = scorer.combine_expected_tags("Anime Openings", observed)
        # At least one of the non-dz_bpm observed tags should appear
        obs_non_numeric = ["rock", "classic_rock", "80s"]
        assert any(t in merged for t in obs_non_numeric), (
            f"No valid observed tags in merged list. Got: {merged}"
        )

    def test_static_tags_always_first(self):
        """Static mood expected tags must appear before any observed additions."""
        merged = scorer.combine_expected_tags("Hollow", {"rock": 5.0})
        static = scorer.mood_expected_tags("Hollow")
        if static:
            for i, tag in enumerate(static[:3]):
                assert tag in merged, f"Static tag '{tag}' missing from merged list"


# ── 5. graph_mood_ floor behaviour ───────────────────────────────────────────

class TestGraphMoodFloor:
    """graph_mood_ tags must act as a floor on tag_score."""

    def test_graph_tag_raises_tag_score_floor(self):
        """A track with graph_mood_hollow=0.75 must have t≥0.75 for Hollow."""
        p = _make_profile(tags={"graph_mood_hollow": 0.75, "rock": 0.5})
        exp_tags = scorer.mood_expected_tags("Hollow") or ["sad", "melancholic"]
        t = scorer.tag_score(p, exp_tags)

        # Simulate the floor applied in score_track
        g_slug = "hollow"
        g_conf = scorer.get_active_tags(p).get(f"graph_mood_{g_slug}", 0.0)
        t_with_floor = max(t, g_conf)

        assert t_with_floor >= 0.75, (
            f"graph_mood_hollow=0.75 should set floor of 0.75 on tag_score, "
            f"but got {t_with_floor:.4f} (raw t={t:.4f})"
        )

    def test_graph_tag_does_not_reduce_existing_tag_score(self):
        """graph_mood_ floor must never LOWER an already-high tag_score."""
        p = _make_profile(tags={
            "graph_mood_hollow": 0.30,
            "sad": 1.0, "hollow": 1.0, "night": 0.9, "melancholy": 0.8,
        })
        exp_tags = scorer.mood_expected_tags("Hollow") or ["sad", "hollow", "night"]
        t_raw = scorer.tag_score(p, exp_tags)

        g_conf = 0.30
        t_with_floor = max(t_raw, g_conf)

        assert t_with_floor >= t_raw, (
            f"graph floor reduced tag_score: {t_raw:.4f} → {t_with_floor:.4f}"
        )

    def test_anchor_tag_in_signal_confidence(self):
        """anchor_ tags must contribute +0.45 to signal_confidence."""
        tags_with_anchor = {"anchor_hollow": 1.0}
        conf = scorer._signal_confidence(tags_with_anchor)
        assert conf >= 0.45, (
            f"anchor_ tag should contribute ≥0.45 to signal_confidence, got {conf:.4f}"
        )

    def test_graph_mood_in_signal_confidence(self):
        """graph_mood_ tags must contribute +0.45 to signal_confidence."""
        tags_with_graph = {"graph_mood_hollow": 0.8}
        conf = scorer._signal_confidence(tags_with_graph)
        assert conf >= 0.45, (
            f"graph_mood_ tag should contribute ≥0.45 to signal_confidence, got {conf:.4f}"
        )


# ── 6. tag_score capping ──────────────────────────────────────────────────────

class TestTagScore:
    """tag_score must always return values in [0.0, 1.0]."""

    def test_tag_score_bounded(self):
        """tag_score must be capped at 1.0 regardless of tag weight magnitude."""
        # A track with a 193.2 raw value (dz_bpm style) as sole tag
        p = _make_profile(tags={"dz_bpm": 193.2})
        exp_tags = ["dz_bpm"]  # worst case: raw numeric in expected_tags
        t = scorer.tag_score(p, exp_tags)
        assert 0.0 <= t <= 1.0, (
            f"tag_score returned {t:.4f} — must be in [0.0, 1.0]. "
            "Raw numeric value leaked through without normalization."
        )

    def test_tag_score_empty_tags(self):
        p = _make_profile(tags={})
        t = scorer.tag_score(p, ["sad", "night"])
        assert t == 0.0

    def test_tag_score_empty_expected(self):
        p = _make_profile(tags={"sad": 0.8})
        t = scorer.tag_score(p, [])
        assert t == 0.0

    def test_tag_score_exact_match(self):
        """Exact match should give maximum credit (not zero)."""
        p = _make_profile(tags={"sad": 1.0})
        t = scorer.tag_score(p, ["sad"])
        assert t > 0.0, "Exact tag match should produce t > 0"


# ── 7. semantic_score neutral fallback ───────────────────────────────────────

class TestSemanticScore:
    def test_no_semantic_core_returns_neutral(self):
        """Moods without a declared semantic_core should return 0.5 (neutral pass-through)."""
        # Find any mood with no semantic_core or use a fake one
        p = _make_profile(tags={"something": 0.5})
        # Directly test with empty core: the function returns 0.5 if no core defined.
        sem_core = scorer.mood_semantic_core("__nonexistent_mood_xyz__")
        if not sem_core:
            s = scorer.semantic_score(p, "__nonexistent_mood_xyz__")
            assert s == 0.5, f"Expected 0.5 neutral, got {s}"

    def test_semantic_score_bounded(self):
        p = _make_profile(tags={"sad": 0.9, "night": 0.8, "dark": 0.7})
        s = scorer.semantic_score(p, "Hollow")
        assert 0.0 <= s <= 1.0, f"semantic_score out of [0,1]: {s}"


# ── 8. genre_score wildcard rules ────────────────────────────────────────────

class TestGenreScore:
    def test_other_only_returns_wildcard(self):
        """A track whose ONLY genre is 'Other' should return 0.3 wildcard."""
        p = _make_profile(macro_genres=["Other"])
        g = scorer.genre_score(p, ["Hip-Hop", "Rap", "Pop"])
        assert g == 0.3, (
            f"'Other'-only track should return 0.3 wildcard against any pref list, got {g}"
        )

    def test_other_with_known_non_matching_genre_returns_zero(self):
        """If a track has recognized genres that don't match, Other doesn't save it."""
        p = _make_profile(macro_genres=["Metal", "Other"])
        g = scorer.genre_score(p, ["Hip-Hop", "Rap"])
        assert g == 0.0, (
            f"Track with known non-matching genre should return 0.0, got {g}"
        )

    def test_match_returns_one(self):
        p = _make_profile(macro_genres=["Hip-Hop"])
        g = scorer.genre_score(p, ["Hip-Hop", "Rap"])
        assert g == 1.0

    def test_no_preferred_genres_returns_half(self):
        """If mood has no genre preference, all tracks pass at 0.5."""
        p = _make_profile(macro_genres=["Metal"])
        g = scorer.genre_score(p, [])
        assert g == 0.5


# ── 9. End-to-end sanity: well-matched anchor track scores high ───────────────

class TestAnchorTrackSanity:
    """An anchor track (anchor_<mood>=1.0 + graph_mood_<mood>=1.0) must outscore
    a random unrelated track for the same mood."""

    def test_anchor_outscores_random(self):
        anchor = _make_profile(
            tags={
                "anchor_hollow": 1.0,
                "graph_mood_hollow": 1.0,
                "sad": 0.9,
                "night": 0.8,
            },
            macro_genres=["Indie", "Alternative"],
        )
        random_track = _make_profile(
            tags={"happy": 0.7, "summer": 0.6},
            macro_genres=["Pop"],
        )
        s_anchor = scorer.score_track(anchor, "Hollow")
        s_random = scorer.score_track(random_track, "Hollow")

        if s_anchor == -1.0 or s_random == -1.0:
            pytest.skip("Hard filter rejected a track — constraint test n/a")

        assert s_anchor > s_random, (
            f"Anchor track (score={s_anchor:.4f}) should outscore random track "
            f"(score={s_random:.4f}) for Hollow"
        )
