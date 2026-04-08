"""
validation_check.py — Post-scan quality gate for the Vibesort Signal System.

Run after a full scan to verify the rebuild targets from SIGNAL_REBUILD_PLAN.md.

Usage:
    python scripts/validation_check.py [--snapshot PATH]

Reads:
    outputs/.last_scan_snapshot.json  (default)
    outputs/.mining_cache.json
    outputs/.deezer_cache.json
    outputs/.lyrics_cache.json

Exit code 0 if all gates pass, 1 if any fail.
"""

from __future__ import annotations

import json
import os
import sys
import statistics

_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUTS = os.path.join(_ROOT, "outputs")


# ── Loader helpers ─────────────────────────────────────────────────────────────

def _load(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"  [WARN] Could not load {path}: {e}")
        return {}


def _load_snapshot(override: str | None = None) -> dict:
    p = override or os.path.join(_OUTPUTS, ".last_scan_snapshot.json")
    data = _load(p)
    if not data:
        print(f"  [ERROR] Snapshot not found or empty: {p}")
        print("  Run a full scan first, then re-run validation_check.py")
        sys.exit(1)
    return data


# ── Metric helpers ─────────────────────────────────────────────────────────────

def _bpm_coverage(snapshot: dict) -> float:
    """Fraction of tracks that have a real Deezer BPM (dz_bpm in track_tags)."""
    track_tags = snapshot.get("track_tags", {})
    if not track_tags:
        return 0.0
    with_bpm = sum(1 for tags in track_tags.values() if tags.get("dz_bpm"))
    return with_bpm / max(len(track_tags), 1)


def _lyr_coverage(snapshot: dict) -> float:
    """Fraction of tracks that have at least one lyr_* tag."""
    track_tags = snapshot.get("track_tags", {})
    if not track_tags:
        return 0.0
    with_lyr = sum(
        1 for tags in track_tags.values()
        if any(k.startswith("lyr_") for k in tags)
    )
    return with_lyr / max(len(track_tags), 1)


def _max_artist_repeat(snapshot: dict) -> int:
    """Max number of times a single artist appears in any one mood playlist."""
    mood_results = snapshot.get("mood_results", {})
    if not mood_results:
        return 0
    all_tracks_meta = snapshot.get("all_tracks", [])
    uri_to_artists: dict[str, list[str]] = {}
    for t in all_tracks_meta:
        uri = t.get("uri", "")
        artists = [a.get("name", "") if isinstance(a, dict) else str(a)
                   for a in (t.get("artists") or [])]
        if uri:
            uri_to_artists[uri] = artists

    max_repeat = 0
    for mood_name, result in mood_results.items():
        tracks = result.get("tracks", [])
        artist_counts: dict[str, int] = {}
        for entry in tracks:
            uri = entry if isinstance(entry, str) else entry.get("uri", "")
            for artist in uri_to_artists.get(uri, []):
                artist_counts[artist] = artist_counts.get(artist, 0) + 1
        if artist_counts:
            max_repeat = max(max_repeat, max(artist_counts.values()))
    return max_repeat


def _score_std_fraction(snapshot: dict, threshold: float = 0.05) -> float:
    """Fraction of populated moods with score std >= threshold."""
    mood_results = snapshot.get("mood_results", {})
    if not mood_results:
        return 0.0
    passing = 0
    total = 0
    for mood_name, result in mood_results.items():
        scores = [
            entry.get("score", 0) if isinstance(entry, dict) else 0
            for entry in result.get("tracks", [])
        ]
        if len(scores) >= 3:
            total += 1
            if statistics.stdev(scores) >= threshold:
                passing += 1
    return passing / max(total, 1)


def _populated_moods(snapshot: dict, min_tracks: int = 5) -> int:
    """Number of moods with >= min_tracks."""
    mood_results = snapshot.get("mood_results", {})
    return sum(
        1 for r in mood_results.values()
        if len(r.get("tracks", [])) >= min_tracks
    )


def _no_single_artist_mood(snapshot: dict, max_fraction: float = 0.60) -> bool:
    """True if no mood playlist is dominated (>max_fraction) by one artist."""
    mood_results = snapshot.get("mood_results", {})
    all_tracks_meta = snapshot.get("all_tracks", [])
    uri_to_artists: dict[str, list[str]] = {}
    for t in all_tracks_meta:
        uri = t.get("uri", "")
        artists = [a.get("name", "") if isinstance(a, dict) else str(a)
                   for a in (t.get("artists") or [])]
        if uri:
            uri_to_artists[uri] = artists

    for mood_name, result in mood_results.items():
        tracks = result.get("tracks", [])
        if len(tracks) < 3:
            continue
        artist_counts: dict[str, int] = {}
        for entry in tracks:
            uri = entry if isinstance(entry, str) else entry.get("uri", "")
            for artist in uri_to_artists.get(uri, []):
                artist_counts[artist] = artist_counts.get(artist, 0) + 1
        if artist_counts:
            dominant_frac = max(artist_counts.values()) / max(len(tracks), 1)
            if dominant_frac > max_fraction:
                print(f"    ⚠  Single-artist mood: {mood_name!r} "
                      f"({max(artist_counts, key=artist_counts.get)}: "
                      f"{max(artist_counts.values())}/{len(tracks)} tracks)")
                return False
    return True


def _mood_overlap(snapshot: dict, mood_a: str, mood_b: str) -> float:
    """Fraction of mood_a tracks that also appear in mood_b (top-10 overlap)."""
    mood_results = snapshot.get("mood_results", {})
    def _uris(name: str) -> set[str]:
        r = mood_results.get(name, {})
        out = set()
        for entry in r.get("tracks", [])[:10]:
            uri = entry if isinstance(entry, str) else entry.get("uri", "")
            if uri:
                out.add(uri)
        return out
    a = _uris(mood_a)
    b = _uris(mood_b)
    if not a:
        return 0.0
    return len(a & b) / len(a)


def _mining_cache_size(snapshot: dict) -> int:
    """Number of track_tags entries in mining cache via snapshot."""
    mc = _load(os.path.join(_OUTPUTS, ".mining_cache.json"))
    return len(mc.get("track_tags", {}))


# ── Gate definitions ───────────────────────────────────────────────────────────

def _run_gates(snapshot: dict) -> list[tuple[str, bool, str]]:
    """
    Returns list of (gate_name, passed, detail_str).
    """
    results = []

    def gate(name: str, passed: bool, detail: str = "") -> None:
        results.append((name, passed, detail))

    # 1 — Mining cache
    mc_size = _mining_cache_size(snapshot)
    gate(
        "Mining cache non-empty (>100 entries)",
        mc_size > 100,
        f"{mc_size} track_tags entries",
    )

    # 2 — Deezer BPM coverage
    bpm = _bpm_coverage(snapshot)
    gate(
        "Deezer BPM coverage >= 50%",
        bpm >= 0.50,
        f"{bpm*100:.1f}%",
    )

    # 3 — lyr_* coverage
    lyr = _lyr_coverage(snapshot)
    gate(
        "lyr_* coverage >= 65%",
        lyr >= 0.65,
        f"{lyr*100:.1f}%",
    )

    # 4 — Artist cap
    max_rep = _max_artist_repeat(snapshot)
    gate(
        "Artist cap enforced (<= 3 tracks per artist per mood)",
        max_rep <= 3,
        f"max repeat = {max_rep}",
    )

    # 5 — Score std
    std_frac = _score_std_fraction(snapshot)
    gate(
        "Score std >= 0.05 for >= 60% of moods",
        std_frac >= 0.60,
        f"{std_frac*100:.1f}% of moods pass",
    )

    # 6 — Populated moods
    pop = _populated_moods(snapshot)
    gate(
        ">= 65 moods populated (>= 5 tracks)",
        pop >= 65,
        f"{pop} moods",
    )

    # 7 — No single-artist mood
    no_single = _no_single_artist_mood(snapshot)
    gate(
        "No mood dominated by one artist (> 60%)",
        no_single,
        "" if no_single else "see warnings above",
    )

    # 8 — Heartbreak vs Villain Arc top-10 overlap
    hb_va = _mood_overlap(snapshot, "Heartbreak", "Villain Arc")
    gate(
        "Heartbreak × Villain Arc top-10 overlap < 40%",
        hb_va < 0.40,
        f"{hb_va*100:.1f}% overlap",
    )

    return results


# ── Manual inspection list ─────────────────────────────────────────────────────

_INSPECT_MOODS = [
    "Heartbreak", "Hollow", "Late Night Drive", "Villain Arc",
    "Overflow", "Healing Kind", "Deep Focus", "Nostalgia",
    "Hard Reset", "Liminal",
]


def _print_mood_inspection(snapshot: dict) -> None:
    mood_results = snapshot.get("mood_results", {})
    all_tracks_meta = snapshot.get("all_tracks", [])
    uri_to_meta: dict[str, dict] = {t.get("uri", ""): t for t in all_tracks_meta if t.get("uri")}

    print("\n── Manual inspection moods ──────────────────────────────────────")
    for mood in _INSPECT_MOODS:
        result = mood_results.get(mood)
        if not result:
            print(f"\n  {mood}: NOT IN RESULTS")
            continue
        tracks = result.get("tracks", [])
        print(f"\n  {mood} ({len(tracks)} tracks):")
        # Artist distribution
        artist_counts: dict[str, int] = {}
        for entry in tracks:
            uri = entry if isinstance(entry, str) else entry.get("uri", "")
            meta = uri_to_meta.get(uri, {})
            for a in (meta.get("artists") or []):
                name = a.get("name", "") if isinstance(a, dict) else str(a)
                if name:
                    artist_counts[name] = artist_counts.get(name, 0) + 1
        top_artists = sorted(artist_counts.items(), key=lambda x: -x[1])[:5]
        if top_artists:
            print(f"    Artists: {', '.join(f'{a}({n})' for a, n in top_artists)}")
        # Top 10 tracks with scores
        for i, entry in enumerate(tracks[:10]):
            if isinstance(entry, dict):
                uri   = entry.get("uri", "")
                score = entry.get("score", 0)
                meta  = uri_to_meta.get(uri, {})
                name  = meta.get("name", uri[-12:] if uri else "?")
                arts  = ", ".join(
                    a.get("name", "") if isinstance(a, dict) else str(a)
                    for a in (meta.get("artists") or [])[:2]
                )
                print(f"    {i+1:2}. [{score:.3f}] {name[:40]} — {arts}")
            else:
                meta  = uri_to_meta.get(entry, {})
                name  = meta.get("name", entry[-12:])
                print(f"    {i+1:2}. {name[:40]}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Vibesort validation gate runner")
    parser.add_argument("--snapshot", default=None, help="Path to scan snapshot JSON")
    parser.add_argument("--inspect", action="store_true", help="Print manual inspection mood lists")
    args = parser.parse_args()

    snapshot = _load_snapshot(args.snapshot)

    print("\n══ Vibesort Signal System — Validation Gates ══════════════════════")
    gates = _run_gates(snapshot)
    all_passed = True
    for name, passed, detail in gates:
        icon  = "✓" if passed else "✗"
        dstr  = f"  ({detail})" if detail else ""
        print(f"  [{icon}] {name}{dstr}")
        if not passed:
            all_passed = False

    if args.inspect:
        _print_mood_inspection(snapshot)

    print()
    if all_passed:
        print("  All gates passed ✓")
    else:
        failed = sum(1 for _, p, _ in gates if not p)
        print(f"  {failed}/{len(gates)} gate(s) failed ✗")

    print("═══════════════════════════════════════════════════════════════════\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
