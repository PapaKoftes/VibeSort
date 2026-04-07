"""
generate_anchors.py — Generate mood_anchors_candidates.json for human review.

Run once from the project root after configuring a Last.fm API key:
    python scripts/generate_anchors.py

What this does:
    1. Reads data/mood_lastfm_tags.json for mood → tag mapping.
    2. Calls lastfm.get_tag_top_tracks() for each mood's PRIMARY tag (index 0).
    3. Takes up to TOP_N results per mood.
    4. Writes data/mood_anchors_candidates.json for human review.

After running:
    - Review the candidates file
    - Remove obvious mismatches / wrong moods
    - Deduplicate: tracks in 3+ moods → keep in the single best-fit mood
    - Add genre-diverse representatives Last.fm missed
    - Rename file to data/mood_anchors.json and commit

Format of output:
    {
      "Heartbreak": [
        {"artist": "Olivia Rodrigo", "title": "drivers license"},
        {"artist": "Alanis Morissette", "title": "You Oughta Know"},
        ...
      ],
      ...
    }
"""

import json
import os
import sys

# Resolve project root regardless of CWD
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core import lastfm as _lf

TOP_N = 25  # candidates per mood

MOOD_TAGS_PATH       = os.path.join(_ROOT, "data", "mood_lastfm_tags.json")
CANDIDATES_OUT_PATH  = os.path.join(_ROOT, "data", "mood_anchors_candidates.json")


def _load_config_key() -> str:
    """Resolve the Last.fm API key from config / .env."""
    try:
        import config as _cfg
        return (
            getattr(_cfg, "VIBESORT_LASTFM_API_KEY", "").strip()
            or getattr(_cfg, "LASTFM_API_KEY", "").strip()
        )
    except Exception as e:
        print(f"[warn] Could not load config: {e}")
        return os.environ.get("LASTFM_API_KEY", "").strip()


def main() -> None:
    api_key = _load_config_key()
    if not api_key:
        print("ERROR: No Last.fm API key found.")
        print("Set LASTFM_API_KEY or VIBESORT_LASTFM_API_KEY in your .env file.")
        sys.exit(1)

    # Load mood → tag mapping
    with open(MOOD_TAGS_PATH, "r", encoding="utf-8") as f:
        mood_lastfm_tags: dict = json.load(f)

    print(f"Generating anchor candidates for {len(mood_lastfm_tags)} moods")
    print(f"Top {TOP_N} tracks per mood from Last.fm tag charts\n")

    cache      = _lf._load_cache()
    candidates = {}
    fetched_tags: dict = {}   # tag → [track dicts] — avoid re-fetching same tag

    total = len(mood_lastfm_tags)
    for i, (mood_name, tags) in enumerate(mood_lastfm_tags.items()):
        if not tags:
            continue
        primary_tag = tags[0]   # only use the first tag for candidates

        if primary_tag not in fetched_tags:
            top = _lf.get_tag_top_tracks(primary_tag, limit=TOP_N, api_key=api_key, cache=cache)
            fetched_tags[primary_tag] = top
        else:
            top = fetched_tags[primary_tag]

        mood_candidates = [
            {"artist": t["artist"], "title": t["title"]}
            for t in top[:TOP_N]
            if t.get("artist") and t.get("title")
        ]
        candidates[mood_name] = mood_candidates

        print(f"  [{i+1:2d}/{total}] {mood_name:<35} {len(mood_candidates)} candidates"
              f" (tag: {primary_tag})")

    _lf._save_cache(cache)

    with open(CANDIDATES_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)
        f.write("\n")

    total_candidates = sum(len(v) for v in candidates.values())
    print(f"\nWrote {total_candidates} candidates across {len(candidates)} moods")
    print(f"Output: {CANDIDATES_OUT_PATH}")
    print("\nNext steps:")
    print("  1. Review data/mood_anchors_candidates.json")
    print("  2. Remove mismatches, deduplicate cross-mood tracks")
    print("  3. Add genre-diverse representatives Last.fm missed")
    print("  4. Rename to data/mood_anchors.json and commit")


if __name__ == "__main__":
    main()
