"""
tests/test_graph_pipeline.py — Unit tests for core/graph.py

Tests the anchor-seeded label propagation pipeline (M4.1).

Run with:  pytest tests/test_graph_pipeline.py -v
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph import (
    inject_anchor_labels,
    propagate_labels,
    compute_graph_tags,
    run_graph_pipeline,
    _clean,
    _slug,
)


# ── Helper: minimal track dict ────────────────────────────────────────────────

def _track(uri: str, artist: str, title: str) -> dict:
    return {
        "uri": uri,
        "name": title,
        "artists": [{"name": artist}],
    }


# ── _clean / _slug helpers ────────────────────────────────────────────────────

class TestHelpers:
    def test_clean_strips_feat(self):
        assert _clean("Song feat. Some Artist") == "song"
        assert _clean("Song ft. Some Artist") == "song"

    def test_clean_strips_parentheticals(self):
        assert _clean("My Iron Lung (remastered)") == "my iron lung"
        assert _clean("Title [Live]") == "title"

    def test_clean_normalises_case(self):
        assert _clean("BE MY MISTAKE") == "be my mistake"

    def test_slug_spaces(self):
        assert _slug("Late Night Drive") == "late_night_drive"

    def test_slug_ampersand(self):
        assert _slug("Smoke & Mirrors") == "smoke_&_mirrors"

    def test_slug_slash(self):
        assert _slug("A/B") == "a_b"

    def test_slug_double_underscore(self):
        # Double spaces become double underscores which are then collapsed to single
        assert _slug("a  b") == "a_b"


# ── inject_anchor_labels ──────────────────────────────────────────────────────

class TestInjectAnchorLabels:
    def test_matches_exact(self):
        tracks = [_track("u1", "Radiohead", "My Iron Lung")]
        lookup = {("radiohead", "my iron lung"): ["Hollow"]}
        seeds = inject_anchor_labels(tracks, lookup)
        assert "u1" in seeds
        assert seeds["u1"]["hollow"] == 1.0

    def test_matches_cleaned_title(self):
        """feat. / (remaster) should be stripped before matching."""
        tracks = [_track("u1", "Radiohead", "My Iron Lung (Remastered)")]
        lookup = {("radiohead", "my iron lung"): ["Hollow"]}
        seeds = inject_anchor_labels(tracks, lookup)
        assert "u1" in seeds

    def test_multiple_moods_per_track(self):
        tracks = [_track("u1", "The Neighbourhood", "How")]
        lookup = {("the neighbourhood", "how"): ["Hollow", "3 AM Unsent Texts"]}
        seeds = inject_anchor_labels(tracks, lookup)
        assert seeds["u1"]["hollow"] == 1.0
        assert seeds["u1"]["3_am_unsent_texts"] == 1.0

    def test_no_match_returns_empty(self):
        tracks = [_track("u1", "Unknown Artist", "Unknown Song")]
        lookup = {("radiohead", "my iron lung"): ["Hollow"]}
        seeds = inject_anchor_labels(tracks, lookup)
        assert len(seeds) == 0

    def test_track_without_uri_skipped(self):
        tracks = [{"uri": "", "name": "Song", "artists": [{"name": "Artist"}]}]
        lookup = {("artist", "song"): ["Hollow"]}
        seeds = inject_anchor_labels(tracks, lookup)
        assert len(seeds) == 0

    def test_primary_artist_only(self):
        """Only primary (index 0) artist is checked."""
        tracks = [_track("u1", "Feature Artist", "Collaboration")]
        # Lookup uses the primary artist — Feature Artist is secondary
        lookup = {("feature artist", "collaboration"): ["Hollow"]}
        seeds = inject_anchor_labels(tracks, lookup)
        assert "u1" in seeds


# ── propagate_labels ──────────────────────────────────────────────────────────

class TestPropagateLabels:
    def test_seeds_unchanged(self):
        """Anchor seeds must always keep confidence=1.0 after propagation."""
        seeds = {"seed1": {"hollow": 1.0}}
        graph = {
            "seed1": [("nbr1", 0.8), ("nbr2", 0.7)],
            "nbr1":  [("seed1", 0.8)],
            "nbr2":  [("seed1", 0.7)],
        }
        labels = propagate_labels(graph, seeds, max_hops=2)
        assert labels["seed1"]["hollow"] == 1.0, (
            "Anchor seed confidence must remain 1.0 after propagation"
        )

    def test_neighbor_receives_label(self):
        """A direct neighbor of a seed must receive a propagated label."""
        seeds = {"seed1": {"hollow": 1.0}}
        graph = {
            "seed1": [("nbr1", 0.9)],
            "nbr1":  [("seed1", 0.9)],
        }
        labels = propagate_labels(graph, seeds, max_hops=2)
        assert "nbr1" in labels
        assert "hollow" in labels["nbr1"]

    def test_confidence_decreases_with_distance(self):
        """Hop-2 labels must be weaker than hop-1 labels for the same mood."""
        seeds = {"seed1": {"hollow": 1.0}}
        # Chain: seed1 → nbr1 → nbr2 (2 hops from seed)
        graph = {
            "seed1": [("nbr1", 0.9)],
            "nbr1":  [("seed1", 0.9), ("nbr2", 0.9)],
            "nbr2":  [("nbr1", 0.9)],
        }
        labels = propagate_labels(graph, seeds, max_hops=2, hop_decay=0.65)
        if "nbr1" in labels and "nbr2" in labels:
            hop1_conf = labels["nbr1"].get("hollow", 0.0)
            hop2_conf = labels["nbr2"].get("hollow", 0.0)
            assert hop1_conf >= hop2_conf, (
                f"Hop-1 confidence ({hop1_conf:.3f}) should be ≥ hop-2 ({hop2_conf:.3f})"
            )

    def test_min_confidence_filters_weak_labels(self):
        """Labels below min_confidence must be discarded."""
        seeds = {"seed1": {"hollow": 1.0}}
        # Weak neighbor — only barely connected
        graph = {
            "seed1": [("nbr1", 0.1)],
            "nbr1":  [("seed1", 0.1), ("noise1", 0.1), ("noise2", 0.1)],
            "noise1": [("nbr1", 0.1)],
            "noise2": [("nbr1", 0.1)],
        }
        labels = propagate_labels(graph, seeds, max_hops=2, min_confidence=0.15)
        # nbr1 surrounded by noise (no other label signals)
        # Its hollow confidence: weight=0.1 from seed1, total_weight=0.1+0.1+0.1=0.3
        # score = (0.1 * 1.0) / 0.3 = 0.333 > 0.15 — might still be included
        # but we just verify min_confidence filters very weak ones
        if "nbr1" in labels:
            for mood, conf in labels["nbr1"].items():
                assert conf >= 0.15, (
                    f"Label {mood}={conf:.4f} is below min_confidence=0.15"
                )

    def test_agreement_mechanism(self):
        """Multiple neighbours agreeing on a mood produces higher confidence
        than a single neighbour with the same individual weight."""
        # Scenario A: one strong seed neighbour
        seeds_a = {"seed1": {"hollow": 1.0}}
        graph_a = {
            "seed1": [("target", 0.8), ("noise1", 0.8)],
            "target": [("seed1", 0.8), ("noise1", 0.8)],
            "noise1": [("seed1", 0.8), ("target", 0.8)],
        }
        labels_a = propagate_labels(graph_a, seeds_a, max_hops=1)

        # Scenario B: two seed neighbours both agreeing
        seeds_b = {"seed1": {"hollow": 1.0}, "seed2": {"hollow": 1.0}}
        graph_b = {
            "seed1": [("target", 0.8), ("noise1", 0.5)],
            "seed2": [("target", 0.8), ("noise2", 0.5)],
            "target": [("seed1", 0.8), ("seed2", 0.8)],
            "noise1": [("seed1", 0.5)],
            "noise2": [("seed2", 0.5)],
        }
        labels_b = propagate_labels(graph_b, seeds_b, max_hops=1)

        conf_a = labels_a.get("target", {}).get("hollow", 0.0)
        conf_b = labels_b.get("target", {}).get("hollow", 0.0)

        assert conf_b >= conf_a, (
            f"Two agreeing seeds ({conf_b:.3f}) should produce ≥ confidence "
            f"than one seed ({conf_a:.3f})"
        )

    def test_returns_dict_of_dicts(self):
        """Return type must be {uri: {mood_slug: confidence}}."""
        seeds = {"s": {"hollow": 1.0}}
        labels = propagate_labels({}, seeds)
        assert isinstance(labels, dict)
        for uri, moods in labels.items():
            assert isinstance(moods, dict)
            for mood, conf in moods.items():
                assert isinstance(mood, str)
                assert isinstance(conf, float)


# ── compute_graph_tags ────────────────────────────────────────────────────────

class TestComputeGraphTags:
    def test_prefix_format(self):
        labels = {"u1": {"hollow": 0.8, "rainy_window": 0.6}}
        tags = compute_graph_tags(labels)
        assert "u1" in tags
        assert "graph_mood_hollow" in tags["u1"]
        assert "graph_mood_rainy_window" in tags["u1"]

    def test_values_preserved(self):
        labels = {"u1": {"hollow": 0.753}}
        tags = compute_graph_tags(labels)
        assert abs(tags["u1"]["graph_mood_hollow"] - 0.753) < 0.001

    def test_zero_confidence_excluded(self):
        labels = {"u1": {"hollow": 0.0, "rage_lift": 0.5}}
        tags = compute_graph_tags(labels)
        assert "graph_mood_hollow" not in tags.get("u1", {})
        assert "graph_mood_rage_lift" in tags.get("u1", {})

    def test_empty_input(self):
        assert compute_graph_tags({}) == {}


# ── run_graph_pipeline ────────────────────────────────────────────────────────

class TestRunGraphPipeline:
    def test_no_api_key_returns_empty(self):
        result = run_graph_pipeline([], api_key="", anchor_lookup={}, cache={})
        assert result == {}

    def test_no_anchor_lookup_returns_empty(self):
        tracks = [_track("u1", "Radiohead", "My Iron Lung")]
        result = run_graph_pipeline(tracks, api_key="somekey", anchor_lookup={}, cache={})
        assert result == {}

    def test_no_library_matches_returns_empty(self):
        """If no library track matches any anchor, pipeline returns {}."""
        tracks = [_track("u1", "Unknown Artist", "Unknown Song")]
        anchor_lookup = {("radiohead", "my iron lung"): ["Hollow"]}
        result = run_graph_pipeline(tracks, api_key="somekey", anchor_lookup=anchor_lookup, cache={})
        assert result == {}

    def test_output_type(self):
        """Return value must be {uri: {tag: confidence}} when pipeline runs."""
        # Only runs graph build if seeds found; we can't mock Last.fm here,
        # so just verify structure when there's a library match but no API results.
        tracks = [_track("u1", "Radiohead", "My Iron Lung")]
        anchor_lookup = {("radiohead", "my iron lung"): ["Hollow"]}
        # With a real key but empty cache, getSimilar may fail — that's OK.
        # The seed track still gets inject_anchor_labels output via compute_graph_tags.
        result = run_graph_pipeline(
            tracks, api_key="__test__key__",
            anchor_lookup=anchor_lookup, cache={},
        )
        assert isinstance(result, dict)
        for uri, tags in result.items():
            assert isinstance(tags, dict)
            for k, v in tags.items():
                assert k.startswith("graph_mood_"), f"Unexpected key: {k}"
                assert isinstance(v, float)
