"""
scripts/validate_all.py

Full pre-release validation. Run from repo root:
    python scripts/validate_all.py

Exits 0 if all checks pass, 1 if any fail.
"""
import json, os, sys, importlib, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
WARN = "\033[93m WARN\033[0m"

failures = []
warnings = []


def check(label, ok, detail="", warn=False):
    if ok:
        print(f"{PASS}  {label}")
    elif warn:
        print(f"{WARN}  {label}" + (f" — {detail}" if detail else ""))
        warnings.append(label)
    else:
        print(f"{FAIL}  {label}" + (f" — {detail}" if detail else ""))
        failures.append(label)


# ── 1. Config / weights ───────────────────────────────────────────────────────
print("\n── Scoring config ──────────────────────────────────────────────────────")
import config as cfg
total_w = round(cfg.W_METADATA_AUDIO + cfg.W_TAGS + cfg.W_SEMANTIC + cfg.W_GENRE, 6)
check("Weights sum to 1.0", abs(total_w - 1.0) < 0.001,
      f"actual={total_w}")
check("MAX_TRACKS_PER_PLAYLIST >= 50", cfg.MAX_TRACKS_PER_PLAYLIST >= 50,
      f"actual={cfg.MAX_TRACKS_PER_PLAYLIST}")
check("MIN_PLAYLIST_TOTAL >= 20", cfg.MIN_PLAYLIST_TOTAL >= 20,
      f"actual={cfg.MIN_PLAYLIST_TOTAL}")

# ── 2. packs.json ─────────────────────────────────────────────────────────────
print("\n── packs.json ──────────────────────────────────────────────────────────")
with open(os.path.join(ROOT, "data", "packs.json"), encoding="utf-8") as f:
    packs = json.load(f)["moods"]

from core.genre import MACRO_GENRES
valid_genres = set(MACRO_GENRES)

bad_refs, thin_tags, empty_genres = [], [], []
for name, mood in packs.items():
    pmg = mood.get("preferred_macro_genres") or []
    for g in pmg:
        if g not in valid_genres:
            bad_refs.append(f"{name}: '{g}'")
    et = mood.get("expected_tags", [])
    if len(et) < 6:
        thin_tags.append(f"{name}: {len(et)} tags")
    if len(pmg) == 0 and name != "Same Vibe Different Genre":
        empty_genres.append(name)

check("No invalid macro genre refs", len(bad_refs) == 0,
      f"{len(bad_refs)} bad: {bad_refs[:3]}")
check("All moods have ≥6 expected_tags", len(thin_tags) == 0,
      f"{len(thin_tags)} thin: {thin_tags[:3]}")
check("No empty preferred_macro_genres", len(empty_genres) == 0,
      f"empty: {empty_genres}")
check("Mood count ≥ 83", len(packs) >= 83,
      f"actual={len(packs)}")

# Warn on moods with <8 tags (target)
thin8 = [n for n, m in packs.items() if len(m.get("expected_tags",[])) < 8]
check("All moods have ≥8 expected_tags (target)", len(thin8) == 0,
      f"{len(thin8)} below target", warn=True)

# ── 3. mood_anchors.json ──────────────────────────────────────────────────────
print("\n── mood_anchors.json ───────────────────────────────────────────────────")
with open(os.path.join(ROOT, "data", "mood_anchors.json"), encoding="utf-8") as f:
    anchors = json.load(f)

pack_names = set(packs.keys())
anchor_names = set(anchors.keys())
check("Mood names consistent between packs and anchors",
      pack_names == anchor_names,
      f"only_packs={pack_names-anchor_names} only_anchors={anchor_names-pack_names}")

thin6 = [(n, len(a)) for n, a in anchors.items() if len(a) < 6]
thin10 = [(n, len(a)) for n, a in anchors.items() if len(a) < 10]
check("All moods have ≥6 anchors", len(thin6) == 0,
      f"{len(thin6)} thin: {[x[0] for x in thin6[:5]]}")
check("All moods have ≥10 anchors (target)", len(thin10) == 0,
      f"{len(thin10)} below target", warn=True)

total_anchors = sum(len(a) for a in anchors.values())
avg_anchors = total_anchors / max(len(anchors), 1)
check("Average anchors ≥ 8 (target)", avg_anchors >= 8,
      f"actual={avg_anchors:.1f}", warn=avg_anchors < 10)

# Check for duplicate anchors within a mood
dupe_moods = []
for name, tracks in anchors.items():
    seen = set()
    for t in tracks:
        key = (t.get("artist","").lower(), t.get("title","").lower())
        if key in seen:
            dupe_moods.append(f"{name}: {t['artist']} - {t['title']}")
        seen.add(key)
check("No duplicate anchors within a mood", len(dupe_moods) == 0,
      f"{dupe_moods[:3]}")

# ── 4. macro_genres.json ──────────────────────────────────────────────────────
print("\n── macro_genres.json ───────────────────────────────────────────────────")
with open(os.path.join(ROOT, "data", "macro_genres.json"), encoding="utf-8") as f:
    mg_raw = json.load(f)
mg_rules = mg_raw.get("rules", mg_raw) if isinstance(mg_raw, dict) else mg_raw
check("macro_genres rule count >= 500", len(mg_rules) >= 500,
      f"actual={len(mg_rules)}")
# Check for duplicate rules
raw_patterns = [r.get("raw","").lower() for r in mg_rules if isinstance(r, dict) and "raw" in r]
dupes = len(raw_patterns) - len(set(raw_patterns))
check("No duplicate macro_genre rules", dupes == 0,
      f"{dupes} duplicate patterns")

# ── 5. Pages importable ───────────────────────────────────────────────────────
print("\n── Page imports ────────────────────────────────────────────────────────")
import glob
pages = sorted(glob.glob(os.path.join(ROOT, "pages", "*.py")))
check("≥9 pages exist", len(pages) >= 9, f"actual={len(pages)}")

# Check no duplicate number prefixes (extract leading digits only)
import re
from collections import Counter
num_prefixes = []
for p in pages:
    m = re.match(r'^(\d+)', os.path.basename(p))
    if m:
        num_prefixes.append(m.group(1))
dup_prefixes = [p for p, c in Counter(num_prefixes).items() if c > 1]
check("No duplicate page number prefixes", len(dup_prefixes) == 0,
      f"duplicates: {dup_prefixes}")

# ── 6. Scan snapshot (if exists) ──────────────────────────────────────────────
print("\n── Scan snapshot ───────────────────────────────────────────────────────")
snap_path = os.path.join(ROOT, "outputs", ".last_scan_snapshot.json")
if os.path.exists(snap_path):
    age_d = (datetime.datetime.now() -
             datetime.datetime.fromtimestamp(os.path.getmtime(snap_path))).days
    check("Snapshot age ≤ 7 days", age_d <= 7,
          f"age={age_d}d", warn=age_d > 7)

    with open(snap_path, encoding="utf-8") as f:
        snap = json.load(f)

    all_tracks = snap.get("all_tracks", [])
    moods_res = snap.get("mood_results", {})
    profiles = snap.get("profiles", {})

    check("Library has tracks", len(all_tracks) > 0, f"count={len(all_tracks)}")

    zero_moods = [n for n, v in moods_res.items()
                  if isinstance(v, dict) and v.get("count", 0) == 0]
    check("Zero zero-result moods", len(zero_moods) == 0,
          f"zero: {zero_moods[:5]}")

    assigned = set()
    for v in moods_res.values():
        if isinstance(v, dict):
            for u in v.get("uris", []):
                assigned.add(u)
    all_uris = {t.get("uri","") for t in all_tracks if isinstance(t, dict)}
    coverage = len(assigned) / max(len(all_uris), 1) * 100
    check("Track coverage ≥ 50%", coverage >= 50,
          f"actual={coverage:.1f}%", warn=coverage < 60)
    check("Track coverage ≥ 70% (target)", coverage >= 70,
          f"actual={coverage:.1f}%", warn=True)

    sizes = [v.get("count", 0) for v in moods_res.values() if isinstance(v, dict)]
    avg_size = sum(sizes) / max(len(sizes), 1)
    check("Average mood size ≥ 30", avg_size >= 30,
          f"actual={avg_size:.0f}", warn=avg_size < 50)

    # Scoring sanity: spot-check 5 random tracks
    from core import scorer
    user_mean = snap.get("user_mean", [0.5]*6)
    import random; random.seed(99)
    sample = random.sample(list(profiles.values()), min(10, len(profiles)))
    bad_scores = 0
    for p in sample:
        s = scorer.score_track(p, "Hollow", user_mean)
        if not (-1.0 <= s <= 1.0):
            bad_scores += 1
    check("Scoring returns values in [-1, 1]", bad_scores == 0,
          f"{bad_scores}/10 out of range")

    # Conflict penalty: should be near 0 for all tracks
    from core.scorer import conflict_penalty
    high_cp = sum(1 for p in profiles.values() if conflict_penalty(p) >= 0.40)
    check("No tracks at max conflict_penalty", high_cp == 0,
          f"{high_cp} tracks at cap", warn=high_cp > 10)
else:
    print(f"{WARN}  No snapshot found — run a scan first")
    warnings.append("No snapshot")

# ── 7. Cache health ───────────────────────────────────────────────────────────
print("\n── Cache health ────────────────────────────────────────────────────────")
cache_checks = {
    "mining":     "outputs/.mining_cache.json",
    "lastfm":     "outputs/.lastfm_cache.json",
    "deezer":     "outputs/.deezer_cache.json",
    "lyrics":     "outputs/.lyrics_cache.json",
}
for name, path in cache_checks.items():
    full = os.path.join(ROOT, path)
    exists = os.path.exists(full)
    check(f"{name} cache present", exists, "run a scan to build", warn=not exists)

# ── 8. Core modules importable ────────────────────────────────────────────────
print("\n── Core module imports ─────────────────────────────────────────────────")
for mod in ["core.scorer", "core.profile", "core.scan_pipeline",
            "core.lastfm", "core.deezer", "core.playlist_mining"]:
    try:
        importlib.import_module(mod)
        check(f"{mod} imports cleanly", True)
    except Exception as e:
        check(f"{mod} imports cleanly", False, str(e))

# Optional ML
try:
    import sentence_transformers
    check("sentence-transformers available", True)
except ImportError:
    check("sentence-transformers available", False,
          "run: pip install sentence-transformers", warn=True)

# semantic_embed module
_sem_path = os.path.join(ROOT, "core", "semantic_embed.py")
check("core/semantic_embed.py exists", os.path.exists(_sem_path))
if os.path.exists(_sem_path):
    try:
        from core.semantic_embed import is_available as _sem_avail
        check("semantic_embed.is_available()", _sem_avail(),
              "sentence-transformers not installed or model not loadable", warn=True)
    except Exception as _se:
        check("semantic_embed imports", False, str(_se))

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n── Summary ─────────────────────────────────────────────────────────────")
print(f"  Failures: {len(failures)}")
print(f"  Warnings: {len(warnings)}")
if failures:
    print(f"\n  FAILED:")
    for f in failures:
        print(f"    ✗ {f}")
if warnings:
    print(f"\n  WARNINGS:")
    for w in warnings:
        print(f"    ⚠ {w}")

print()
if not failures:
    print("\033[92m  All checks passed.\033[0m" +
          (f" ({len(warnings)} warnings)" if warnings else ""))
    sys.exit(0)
else:
    print(f"\033[91m  {len(failures)} check(s) failed.\033[0m")
    sys.exit(1)
