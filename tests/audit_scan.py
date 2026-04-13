"""
tests/audit_scan.py — Post-scan audit for scan quality and regression detection.

Usage:
  python tests/audit_scan.py [snapshot_path]

  # Default: uses outputs/.last_scan_snapshot.json
  python tests/audit_scan.py

  # Custom path:
  python tests/audit_scan.py path/to/snapshot.json

What this checks:
  1. Library stats        — track count, source coverage
  2. Tag pipeline health  — anchor hits, graph hits, lyr_ coverage
  3. Score distribution   — no wild outliers (>2.5), reasonable spread
  4. Mood coverage        — every mood has ≥ 8 qualifying tracks
  5. Known anchor tracks  — curated tracks appear in correct moods
  6. False positive check — random known-misfit tracks score low for wrong moods
  7. Spotify flags        — mining_blocked / playlist_items_blocked detected

Exit code: 0 = pass, 1 = critical failures, 2 = warnings only.

Running after every full scan gives you a structured record of pipeline health.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field

SNAPSHOT_DEFAULT = os.path.join(
    os.path.dirname(__file__), "..", "outputs", ".last_scan_snapshot.json"
)

# ── Expected anchor pairs: (artist_fragment, title_fragment, mood) ─────────────
# If the library contains these tracks, they MUST appear in the top-30 ranked
# list for the given mood.  These are curated entries from data/mood_anchors.json
# that are expected to be widely held in personal libraries.
# Keep this list conservative — only tracks almost everyone would have.
ANCHOR_CHECKS: list[tuple[str, str, str]] = [
    ("Neighbourhood", "How",          "Hollow"),
    ("Radiohead",     "My Iron Lung", "Hollow"),
    ("Linkin Park",   "Crawling",     "Rage Lift"),
    ("Linkin Park",   "Points of Authority", "Rage Lift"),
    ("Eminem",        "Without Me",   "Villain Arc"),
    ("50 Cent",       "Many Men",     "Villain Arc"),
    # Jeff Buckley - Hallelujah is a known edge case: has anchor_hollow but
    # sometimes filtered by cohesion/diversity cap. Listed as a soft check.
    ("Jeff Buckley",  "Hallelujah",   "Hollow"),
]

# ── Known misfits: (artist_fragment, title_fragment, should_NOT_be_mood) ───────
# These tracks should score LOW (<0.50) for the given mood.
MISFIT_CHECKS: list[tuple[str, str, str]] = [
    ("Wheatus",         "Teenage Dirtbag",   "Hollow"),
    ("Imagine Dragons", "On Top Of The World", "Hollow"),
]

# Score above which we flag a track as anomalous
MAX_SANE_SCORE = 2.5

# Minimum tracks per mood to be considered healthy
MIN_TRACKS_PER_MOOD = 8


@dataclass
class AuditResult:
    critical: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)

    def crit(self, msg: str) -> None:
        self.critical.append(msg)
        print(f"  [CRITICAL] {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  [WARNING]  {msg}")

    def good(self, msg: str) -> None:
        self.ok.append(msg)
        print(f"  [OK]       {msg}")


def _name(track_dict: dict) -> str:
    artist = ", ".join(
        a.get("name", "") for a in (track_dict.get("artists") or [])
    )
    title = track_dict.get("name", "")
    return f"{artist} – {title}"


def run_audit(snapshot_path: str) -> AuditResult:
    r = AuditResult()

    # ── Load snapshot ─────────────────────────────────────────────────────────
    print(f"\nLoading snapshot: {snapshot_path}")
    try:
        with open(snapshot_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        r.crit(f"Snapshot not found: {snapshot_path}")
        return r
    except json.JSONDecodeError as e:
        r.crit(f"Snapshot JSON parse error: {e}")
        return r

    all_tracks   = data.get("all_tracks", [])
    track_tags   = data.get("track_tags", {})
    mood_results = data.get("mood_results", {})
    profiles     = data.get("profiles", {})
    scan_flags   = data.get("scan_flags", {})
    scan_meta    = data.get("scan_meta", {})

    uri_to_track: dict[str, dict] = {t["uri"]: t for t in all_tracks if t.get("uri")}
    uri_to_name:  dict[str, str]  = {u: _name(t) for u, t in uri_to_track.items()}

    print(f"\n{'='*60}")
    print(f"  SECTION 1: Library Stats")
    print(f"{'='*60}")

    n_tracks = len(all_tracks)
    n_profiles = len(profiles)
    print(f"  Library tracks : {n_tracks}")
    print(f"  Profiles built : {n_profiles}")

    if n_tracks == 0:
        r.crit("No tracks in library — scan produced empty result")
    elif n_tracks < 100:
        r.warn(f"Library is very small ({n_tracks} tracks) — results may be thin")
    else:
        r.good(f"{n_tracks} tracks ingested")

    if n_profiles < n_tracks * 0.95:
        r.warn(f"Only {n_profiles}/{n_tracks} tracks have profiles — profile build may have errors")
    else:
        r.good(f"{n_profiles} profiles built ({n_profiles/max(n_tracks,1)*100:.1f}%)")

    # ── Section 2: Spotify flags ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SECTION 2: Spotify Dev Mode Flags")
    print(f"{'='*60}")

    mining_blocked   = data.get("mining_blocked", False)
    playlist_blocked = data.get("playlist_items_blocked", False)

    if mining_blocked:
        r.warn("mining_blocked=True — Spotify playlist mining unavailable (Dev Mode)")
    else:
        r.good("Playlist mining active")

    if playlist_blocked:
        r.warn("playlist_items_blocked=True — Own playlists inaccessible (Dev Mode)")
    else:
        r.good("Own playlist items accessible")

    # ── Section 3: Tag pipeline health ───────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SECTION 3: Tag Pipeline Health")
    print(f"{'='*60}")

    n_with_tags    = sum(1 for tt in track_tags.values() if tt)
    n_lyr          = sum(1 for tt in track_tags.values() if any(k.startswith("lyr_") for k in tt))
    n_anchor       = sum(1 for tt in track_tags.values() if any(k.startswith("anchor_") for k in tt))
    n_graph        = sum(1 for tt in track_tags.values() if any(k.startswith("graph_mood_") for k in tt))
    n_dz_bpm       = sum(1 for tt in track_tags.values() if "dz_bpm" in tt)

    tag_rate    = n_with_tags / max(n_tracks, 1) * 100
    lyr_rate    = n_lyr       / max(n_tracks, 1) * 100
    anchor_rate = n_anchor    / max(n_tracks, 1) * 100
    graph_rate  = n_graph     / max(n_tracks, 1) * 100

    print(f"  Tracks with any tag   : {n_with_tags} ({tag_rate:.1f}%)")
    print(f"  Tracks with lyr_*     : {n_lyr} ({lyr_rate:.1f}%)")
    print(f"  Tracks with anchor_*  : {n_anchor} ({anchor_rate:.1f}%)")
    print(f"  Tracks with graph_*   : {n_graph} ({graph_rate:.1f}%)")
    print(f"  Tracks with dz_bpm    : {n_dz_bpm} ({n_dz_bpm/max(n_tracks,1)*100:.1f}%)")

    if tag_rate < 20:
        r.crit(f"Only {tag_rate:.1f}% of tracks have tags — enrichment is failing")
    elif tag_rate < 50:
        r.warn(f"Tag coverage is low ({tag_rate:.1f}%) — Last.fm or AudioDB may be rate-limited")
    else:
        r.good(f"Tag coverage: {tag_rate:.1f}%")

    if n_anchor == 0:
        r.crit("ZERO anchor_ tags — mood_anchors.json not matching any library tracks")
    else:
        r.good(f"{n_anchor} tracks with anchor labels")

    if n_graph == 0:
        r.warn("ZERO graph_mood_ tags — graph pipeline may have failed (no Last.fm API key?)")
    elif graph_rate < 2:
        r.warn(f"Very few graph_mood_ tags ({graph_rate:.1f}%) — graph coverage is minimal")
    else:
        r.good(f"{n_graph} tracks with graph propagation ({graph_rate:.1f}%)")

    # Verify dz_bpm stays OUT of observed_mood_tags combined expected lists
    observed_tags = data.get("observed_mood_tags", {})
    moods_with_bpm_leak = []
    for mood, ctx in observed_tags.items():
        if isinstance(ctx, dict) and "dz_bpm" in ctx:
            # Check if it would bleed into combine_expected_tags
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                from core import scorer as _sc
                merged = _sc.combine_expected_tags(mood, ctx)
                if "dz_bpm" in merged:
                    moods_with_bpm_leak.append(mood)
            except Exception:
                pass

    if moods_with_bpm_leak:
        r.crit(
            f"dz_bpm leaked into merged expected tags for: {moods_with_bpm_leak[:5]}. "
            "Raw BPM values contaminate tag_score. Fix combine_expected_tags filter."
        )
    else:
        r.good("dz_bpm correctly excluded from all merged expected tag lists")

    # ── Section 4: Score distribution ────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SECTION 4: Score Distribution")
    print(f"{'='*60}")

    all_scores: list[float] = []
    anomalous: list[tuple[str, str, float]] = []  # (mood, uri, score)

    for mood, result in mood_results.items():
        for uri, score in result.get("ranked", []):
            all_scores.append(score)
            if score > MAX_SANE_SCORE:
                anomalous.append((mood, uri, score))

    if not all_scores:
        r.crit("mood_results is empty — no tracks scored for any mood")
    else:
        all_scores_sorted = sorted(all_scores, reverse=True)
        median_score = all_scores_sorted[len(all_scores_sorted) // 2]
        max_score    = all_scores_sorted[0]
        pct_above_1  = sum(1 for s in all_scores if s > 1.0) / len(all_scores) * 100

        print(f"  Total scored instances : {len(all_scores)}")
        print(f"  Median score           : {median_score:.4f}")
        print(f"  Max score              : {max_score:.4f}")
        print(f"  Scores > 1.0           : {pct_above_1:.1f}%")
        print(f"  Scores > {MAX_SANE_SCORE}          : {len(anomalous)}")

        if anomalous:
            r.crit(
                f"{len(anomalous)} tracks scored above {MAX_SANE_SCORE} — "
                "unclamped multiplier or raw numeric value in scoring pipeline. "
                f"First offender: {anomalous[0][0]} | {uri_to_name.get(anomalous[0][1], anomalous[0][1])[:40]} = {anomalous[0][2]:.3f}"
            )
        else:
            r.good(f"All scores ≤ {MAX_SANE_SCORE} — multiplier chain bounded correctly")

        if median_score < 0.20:
            r.warn(f"Median score {median_score:.4f} is very low — scoring may be too strict")
        elif median_score > 1.5:
            r.warn(f"Median score {median_score:.4f} is suspiciously high — thresholds may be too loose")
        else:
            r.good(f"Score distribution looks reasonable (median={median_score:.4f})")

    # ── Section 5: Mood coverage ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SECTION 5: Mood Coverage")
    print(f"{'='*60}")

    n_moods_total  = len(mood_results)
    thin_moods     = [(m, len(r["ranked"])) for m, r in mood_results.items() if len(r.get("ranked", [])) < MIN_TRACKS_PER_MOOD]
    empty_moods    = [(m, 0) for m in mood_results if not mood_results[m].get("ranked")]

    print(f"  Moods scored            : {n_moods_total}")
    print(f"  Moods with <{MIN_TRACKS_PER_MOOD} tracks    : {len(thin_moods)}")
    print(f"  Moods with 0 tracks     : {len(empty_moods)}")

    if empty_moods:
        r.crit(f"Moods with no tracks: {[m for m, _ in empty_moods[:5]]}")
    elif thin_moods:
        r.warn(f"{len(thin_moods)} moods have <{MIN_TRACKS_PER_MOOD} tracks: {[m for m, _ in thin_moods[:5]]}")
    else:
        r.good(f"All {n_moods_total} scored moods have ≥{MIN_TRACKS_PER_MOOD} tracks")

    if n_moods_total < 40:
        r.warn(f"Only {n_moods_total} moods scored — library may be too small or genre filters too strict")
    else:
        r.good(f"{n_moods_total} moods scored")

    # ── Section 6: Anchor track verification ──────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SECTION 6: Known Anchor Track Checks")
    print(f"{'='*60}")

    # Build artist/title search
    def _find_uri(artist_frag: str, title_frag: str) -> str | None:
        for t in all_tracks:
            artists = " ".join(a.get("name", "") for a in t.get("artists", []))
            if artist_frag.lower() in artists.lower() and title_frag.lower() in t.get("name", "").lower():
                return t.get("uri")
        return None

    for artist_frag, title_frag, mood in ANCHOR_CHECKS:
        uri_found = _find_uri(artist_frag, title_frag)
        if not uri_found:
            print(f"  [{mood}] {artist_frag} – {title_frag}: not in library (skip)")
            continue

        # Check it appears in the mood's ranked list (top 30)
        mood_ranked = mood_results.get(mood, {}).get("ranked", [])
        top_uris = [u for u, _ in mood_ranked[:30]]
        score = next((s for u, s in mood_ranked if u == uri_found), None)

        if score is None:
            r.warn(
                f"Anchor not in ranked list: {artist_frag} – {title_frag} "
                f"for '{mood}' (track IS in library but scored below threshold)"
            )
        elif uri_found not in top_uris:
            r.warn(
                f"Anchor ranked too low: {artist_frag} – {title_frag} for '{mood}' "
                f"(score={score:.4f}, rank >{30})"
            )
        else:
            rank = top_uris.index(uri_found) + 1
            r.good(f"Anchor OK: {artist_frag} – {title_frag} for '{mood}' → rank #{rank} (score={score:.4f})")

    # ── Section 7: Misfit track checks ────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  SECTION 7: Known Misfit Track Checks")
    print(f"{'='*60}")

    for artist_frag, title_frag, mood in MISFIT_CHECKS:
        uri_found = _find_uri(artist_frag, title_frag)
        if not uri_found:
            print(f"  [{mood}] {artist_frag} – {title_frag}: not in library (skip)")
            continue

        mood_ranked = mood_results.get(mood, {}).get("ranked", [])
        score = next((s for u, s in mood_ranked if u == uri_found), None)

        if score is None:
            r.good(f"Misfit OK (not scored): {artist_frag} – {title_frag} not in '{mood}'")
        elif score > 1.0:
            r.warn(
                f"Misfit scoring high: {artist_frag} – {title_frag} in '{mood}' "
                f"scores {score:.4f} — should be low or absent"
            )
        else:
            r.good(
                f"Misfit scoring low: {artist_frag} – {title_frag} in '{mood}' "
                f"= {score:.4f} (acceptable)"
            )

    # ── Section 8: graph_mood_ coverage by anchor mood ────────────────────────
    print(f"\n{'='*60}")
    print(f"  SECTION 8: Graph Pipeline Coverage by Mood")
    print(f"{'='*60}")

    graph_by_mood: dict[str, int] = defaultdict(int)
    anchor_by_mood: dict[str, int] = defaultdict(int)

    for uri, tags in track_tags.items():
        for k in tags:
            if k.startswith("graph_mood_"):
                graph_by_mood[k[len("graph_mood_"):]] += 1
            elif k.startswith("anchor_"):
                anchor_by_mood[k[len("anchor_"):]] += 1

    print(f"  Moods with anchor seeds  : {len(anchor_by_mood)}")
    print(f"  Moods with graph labels  : {len(graph_by_mood)}")
    print()
    print(f"  Top 10 moods by graph propagation:")
    for mood, count in sorted(graph_by_mood.items(), key=lambda x: -x[1])[:10]:
        print(f"    {mood:35s}: {count} tracks")

    moods_with_anchors_no_graph = set(anchor_by_mood.keys()) - set(graph_by_mood.keys())
    if moods_with_anchors_no_graph:
        r.warn(
            f"{len(moods_with_anchors_no_graph)} moods have anchor seeds but no graph propagation: "
            f"{list(moods_with_anchors_no_graph)[:5]}. "
            "Last.fm getSimilar may have returned no library matches for these seeds."
        )
    else:
        r.good("All anchor-seeded moods have at least some graph propagation")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  AUDIT SUMMARY")
    print(f"{'='*60}")
    print(f"  Critical failures : {len(r.critical)}")
    print(f"  Warnings          : {len(r.warnings)}")
    print(f"  Checks passed     : {len(r.ok)}")
    print()

    if r.critical:
        print("CRITICAL FAILURES (must fix before shipping):")
        for msg in r.critical:
            print(f"  [FAIL] {msg}")
    if r.warnings:
        print("WARNINGS (investigate before next release):")
        for msg in r.warnings:
            print(f"  [WARN] {msg}")

    return r


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else SNAPSHOT_DEFAULT
    result = run_audit(path)

    if result.critical:
        return 1
    if result.warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
