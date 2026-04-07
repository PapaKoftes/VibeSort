# Vibesort — Signal System Rebuild Plan

**Status:** In progress
**Target:** Fully working per-track signal system for any public user
**Milestone count:** 3 phases, 12 milestones + packs cleanup, 1 final validation gate

---

## Problem Statement

The pre-Phase-1 system worked because Spotify allowed public playlist fetching (`playlist_items`).
That gave the system a human-curated mood signal: real people had assembled "heartbreak playlist,"
"late night drive," etc. Those tracks became ground truth for each mood.

Two things then died simultaneously:
1. **Spotify audio features** (`/audio-features`) — deprecated November 2024, returns 403 always.
2. **Spotify public playlist mining** — permanently blocked in Development Mode. Policy, not rate limit.

With both gone, only tag enrichment remained. But enrichment is almost entirely **artist-level**
(Last.fm artist tags, Deezer artist genres, AudioDB artist moods). Every track from the same
artist gets the same tags → same score → mood playlists collapse to a single artist repeated N times.

**The fix is not to patch individual bugs. It is to rebuild the signal stack from scratch**,
replacing dead sources with living equivalents and adding per-track signals that actually
differentiate songs within an artist's catalog.

---

## Final Output Definition

When this plan is complete, the system shall:

1. **Produce meaningful mood playlists for any public user** with no optional API keys. Spotify
   OAuth + the shared Last.fm key is sufficient for full operation.

2. **Differentiate tracks within an artist's catalog.** "When I'm Gone" (Eminem) and "Without Me"
   (Eminem) must not score identically. At minimum 70% of artists with 5+ library tracks shall
   have measurable score variance across moods.

3. **Enforce artist diversity.** No mood playlist shall contain more than 3 tracks from the same
   artist after all pipeline stages.

4. **Score moods with real spread.** At least 60% of populated moods shall have score std ≥ 0.05.
   Current baseline: 18% (14/79 moods). Target: ≥ 47 moods.

5. **Populate at least 65 of 87 moods** for a library of 2,000+ tracks.

6. **Make first-scan latency transparent.** Every slow enrichment step shall print what it is
   doing, why it is slow on first run, and that cached results will make future scans fast.

7. **Respect caches across rescans.** Enrichment data that does not change (lyrics, BPM, genre
   tags, audio fingerprints) shall never be re-fetched unless the user explicitly requests it.
   Only mood scoring (the final pipeline stage) re-runs on rescan.

8. **Support three scan modes** with clear UX: Full Scan, Custom Scan, Local Library Scan.

9. **Pass all existing tests** and the new validation checklist defined in Phase 3.

---

## Architecture Overview

```
INPUT SOURCES (what we fetch)
  ├── Spotify          → track list, artist names, album metadata, popularity
  ├── Last.fm          → artist tags, per-track tags, tag.getTopTracks (mood ground truth)
  ├── Deezer           → artist genres, per-track BPM + explicit + rank + contributors
  ├── AudioDB          → artist mood/style, per-track mood/theme (uncapped)
  ├── MusicBrainz      → recording-level genre/mood tags
  ├── lrclib.net       → full lyrics for entire library (no cap, no key)
  └── User's own data  → named playlists, local files (AcoustID → MusicBrainz)

SIGNAL EXTRACTION (what we derive per track)
  ├── lyr_*            → mood tags from lyrics × NRC Emotion Lexicon × VADER valence
  ├── bpm_*            → tempo bucket from Deezer BPM (real data)
  ├── meta_*           → title keywords, duration bucket, explicit flag, track position, feat. artists
  ├── mood_*           → Last.fm tag.getTopTracks match (track is in human-curated mood list)
  ├── anchor_*         → curated anchor track match (track is known ground truth for mood)
  └── artist_*         → inherited artist-level signals (fallback only)

CONFIDENCE LAYERS
  ├── High (1.0×)      → lyr_*, bpm_*, mood_* (from Last.fm tag charts), anchor_*
  ├── Medium (0.85×)   → meta_*, per-track AudioDB, MusicBrainz recording tags
  └── Low (0.7×)       → artist-level signals when per-track data exists for that track

SCORING
  ├── tag_score        → expected_tags vs active_tags with confidence-weighted claimed dict
  ├── semantic_score   → mood semantic core match
  ├── genre_score      → macro genre alignment
  └── audio_score      → proxy vector (BPM-anchored tempo, VADER-informed valence)

OUTPUT
  └── mood_results     → ranked playlists, 20-50 tracks, max 3 per artist, std ≥ 0.05 target
```

---

## Phase 1 — Foundation

**Goal:** Remove everything dead, restore the human-curated mood signal, maximize per-track data
acquisition, redesign scan UX.

**Exit criteria:** A scan produces visibly different results per mood. Heartbreak does not consist
of only one artist. Mining cache is non-empty. packs.json cross-contamination removed.

---

### M1.0 — packs.json Mood Definition Cleanup

**What:**
Fix cross-contamination between mood definitions that causes wrong scoring matches.

Confirmed bug: Heartbreak has `"angry"` in both `expected_tags` AND `semantic_core`.
`"angry"` is also a core expected tag for Villain Arc. This causes Heartbreak to match
heavily on angry tracks (they exist in Villain Arc playlists, not Heartbreak ones).

Fix: Remove `"angry"` from Heartbreak `expected_tags` — it is already in `semantic_core`
which is sufficient context. Remove any other expected_tags entries that clearly belong to
a different mood and are causing phantom inflation.

Full audit of all 87 moods:
1. For each mood, check its `expected_tags` list against every other mood's `expected_tags`
2. Flag any tag that appears in 3+ mood definitions (over-broad signal)
3. Remove or weight-reduce these from secondary moods that shouldn't own them

**Why first:** Mood definition bugs corrupt every downstream scoring step. This is a
zero-cost fix (no API, no pipeline) and must happen before we add more signals on top of
broken foundations.

**Scope — this is larger than it looks.** A full audit of packs.json reveals:
- 63 tags appear in 3+ mood definitions (severely diluted signal)
- `"introspective"` in 17 moods — too broad, removes differentiation
- `"dark"` in 13 moods — three incompatible meanings: atmospheric, aggressive, heavy
- `"melancholic"` in 12 moods — incorrectly used in cozy/anxious/bittersweet moods
- `"angry"` in 9 moods — belongs in Villain Arc / Adrenaline / Rage Lift / Drill / Hard Reset;
  must be removed from Heartbreak, Emo Hour, Raw Emotion, Punk Sprint
- `"hype"` in 9 moods — contradictory in Rage Lift and all Anime moods

**Priority fixes (directly causes wrong playlist output):**
1. Remove `"angry"` from: Heartbreak, Emo Hour, Raw Emotion, Punk Sprint
2. Remove `"hype"` from: Rage Lift, Anime OST Energy, Anime Openings, Kawaii Metal Sparkle
3. Remove `"melancholic"` from: Acoustic Corner, Overthinking, Rainy Window, Goth/Darkwave, Sundown
   (it fits: Heartbreak, Hollow, Dark Pop, Shoegaze Breakups, Nostalgia — bittersweet only)
4. Audit all moods with 4+ of the diluted-signal tags and remove the least-specific ones

**Time estimate:** This is a ~2–3 hour careful audit, not a quick fix.

**Validation:** `"angry"` does not appear in Heartbreak's `expected_tags`.
Heartbreak and Villain Arc top-10 track overlap < 40%. No tag appears in more than 6 moods.

---

### M1.1 — Remove Dead Code (Audio Features + W_AUDIO)

**What:**
Remove the Spotify `/audio-features` dead API dependency and the zombie `W_AUDIO = 0.0`
constant, and correctly wire the proxy weight into the scorer.

**Background (important — read before touching scorer.py):**
`config.py` already has TWO audio weight constants:
- `W_AUDIO = 0.0` — the dead Spotify audio features weight (zombie constant, remove it)
- `W_METADATA_AUDIO = 0.10` — the active metadata proxy weight (keep this, it works)

`scorer.py`'s `effective_score_weights()` (lines 356–374) already handles the proxy case:
when `audio_vector_source == "metadata_proxy"`, it **overrides** the incoming `w_audio` slot
with `W_METADATA_AUDIO = 0.10` and rescales the remaining 3 weights proportionally.
This means **the proxy audio score is already contributing 10% to all track scores** today.
The M1.1 change to scorer.py is therefore **cleanup only** — not a scoring fix.

`scan_pipeline.py` lines 917–937 build `_weights = (0.0, _w_tags, _w_sem, _w_gen)` hardcoded
with `0.0` for the audio slot. After removing `W_AUDIO` from config, replace these `0.0`
literals with `cfg.W_METADATA_AUDIO` for clarity — behavior is unchanged (effective_score_weights
handles proxy override regardless), but the code now correctly expresses intent.

**Files and exact changes:**

`config.py`:
- Remove the line `W_AUDIO = 0.0` and its comment. `W_METADATA_AUDIO` stays unchanged.

`core/scorer.py` (5 references):
- Line 41: `W_AUDIO = _cfg.W_AUDIO` → `W_METADATA_AUDIO = _cfg.W_METADATA_AUDIO`
- Lines 99, 1074, 1161, 1666: Replace `W_AUDIO` in each weight tuple with `W_METADATA_AUDIO`
- The 4-tuple `(W_AUDIO, W_TAGS, W_SEMANTIC, W_GENRE)` becomes
  `(W_METADATA_AUDIO, W_TAGS, W_SEMANTIC, W_GENRE)` — a rename of the audio slot, not a deletion.
  The total still sums to 1.0 (0.10 + 0.46 + 0.26 + 0.18).

`core/enrich.py`:
- Replace `audio_features()` function body with `return {}` stub.
- Keep the function signature (callers pass through cleanly, return empty dict, no 403 call).

`core/scan_pipeline.py`:
- Remove `W_AUDIO` import. Keep `W_METADATA_AUDIO` import.
- The `audio_features_map` variable stays as an empty dict — no callers break.

`core/audio_proxy.py`:
- The parameter `audio_features_map` is still passed in (from profile.py and scan_pipeline.py).
  With real Spotify features gone, the function already falls back to metadata_proxy for all tracks.
  No logic changes needed — the parameter just receives an empty dict.

`core/audio_groups.py` — **NO CHANGES NEEDED**:
- `has_real_audio()` already returns `False` (all tracks use metadata_proxy).
- The code already runs the `genre_inference` fallback path for every track.
- The string literals `"source": "audio_features"` are unreachable dead labels — harmless.
- Touching this file risks breaking the working fallback path. Leave it alone.

`core/recommend.py` — **NO CHANGES NEEDED**:
- The `sp.audio_features(batch)` call already catches 403 gracefully (line 136) and continues.
- Returns empty dict for candidates, recommend path still works without audio data.

`core/profile.py` — **NO CHANGES NEEDED**:
- `audio_features_map.get(uri, {})` returns `{}` → `_audio_vector({})` returns neutral sentinel.
- Already fully handles missing audio data. No changes required.

`pages/8_Stats.py`, `pages/3_Vibes.py`, `run.py`:
- These read `"audio_features"` from the snapshot dict. Verify each uses `.get("audio_features", {})`
  (they do). No changes needed — they display nothing when the key is empty.

`pages/9_Settings.py`:
- Remove the Spotify audio features UI toggle if it exists.

**What to keep / NOT touch:**
- `core/acoustid.py` — DO NOT DELETE. It will be properly wired in M1.6.
- `ACOUSTID_API_KEY`, `FPCALC_PATH`, `LOCAL_MUSIC_PATH` in config — DO NOT REMOVE. M1.6 uses them.
- `core/rym.py` — active when user provides CSV export, works correctly
- `core/beets.py` — wired and working, leave it alone
- `W_METADATA_AUDIO` in config — DO NOT REMOVE. It is the active proxy weight.

**Validation:** `grep -rn "W_AUDIO" core/ config.py pages/` returns zero results.
`grep -rn "\.audio_features(" core/` returns zero results (the stub function itself is OK).
Running `python -c "from core import scorer, config; print(sum([config.W_METADATA_AUDIO, config.W_TAGS, config.W_SEMANTIC, config.W_GENRE]))"` prints `1.0`.

---

### M1.2 — Deezer Per-Track Data

**What:**
Extend `core/deezer.py` with `get_track_data_batch(tracks: list[dict]) -> dict[str, dict]`.

Strategy per track:
```
Deezer /search?q=artist:"<name>" track:"<title>"&limit=5
  → pick best match by title similarity + artist match
  → extract: bpm (int|None), explicit_lyrics (bool), rank (int), gain (float)
  → extract contributors: [{name, role}] — feat. artists live here
```

**Non-English matching strategy (critical for K-pop, Arabic, J-pop, etc.):**
```
Attempt 1: artist:"<original_name>" track:"<original_title>"
Attempt 2: If 0 results → drop quotes: artist:<name> track:<title>
Attempt 3: If 0 results → title only: track:"<title>" (if title is ASCII)
Attempt 4: If still 0 → skip, log as "no Deezer match" in cache
```
Use `difflib.SequenceMatcher` for fuzzy title matching on returned results.
Accept match if title similarity ≥ 0.8 AND artist similarity ≥ 0.7.

Then add `get_artist_top_tracks(artist_name: str, limit: int = 50) -> list[dict]` using
`/search?q=artist:"<name>"&limit=50` for bulk BPM acquisition.

**`_load_cache()` must be updated** — currently only initializes `{"artists": {}}`.
Add `"tracks": {}` to the default so per-track cache writes don't fail silently:
```python
return {"artists": {}, "tracks": {}}  # was: {"artists": {}} only
```

Cache structure in `.deezer_cache.json`:
```json
{
  "artists": { "<artist_lower>": ["Genre1", "Genre2"] },
  "tracks":  { "<artist_lower>|||<title_lower>": { "bpm": 128, "explicit": true, "rank": 847000 } }
}
```

Rate: keep 150ms gap. Tracks cached permanently (BPM doesn't change).

First-run messaging: "Fetching per-track audio data from Deezer — this runs once and is
cached permanently. Approx. [N] seconds for your library."

**Validation:** `.deezer_cache.json` has a `"tracks"` key with entries. BPM is non-null
for > 50% of mainstream artists. K-pop or J-pop artists in library are attempted with
fallback strategy and result logged.

---

### M1.3 — Last.fm Tag Charts as Mood Ground Truth

**What:**
Replace the dead Spotify public playlist mining path with Last.fm `tag.getTopTracks`.

Last.fm's API: `tag.getTopTracks(tag="heartbreak", limit=100)` returns the 100 tracks
the community has most associated with that tag. This replaces Spotify playlist mining.

Implementation in `core/playlist_mining.py`:
1. For each mood, map its `seed_phrases` to Last.fm tag vocabulary
   (e.g., "heartbreak playlist" → tags: ["heartbreak", "breakup", "sad breakup"])
2. Call `tag.getTopTracks` for each tag (up to 3 per mood, limit=100 each)
3. Deduplicate, normalize (artist+title → lowercase)
4. Cross-reference against user's library: any matching track gets `mood_<moodname>` tag
5. Tracks not in library → stored in `track_context` for the `combine_expected_tags` feedback loop
6. Cache in `.mining_cache.json` with **30-day TTL** — explicitly set `CACHE_TTL_DAYS = 30`
   in `playlist_mining.py` (current code has 7-day TTL; tag.getTopTracks results are stable
   and fetching 87 moods × 3 tags × 100 tracks on every 7-day expire is too aggressive)

Implement `lastfm.py:get_tag_top_tracks(tag: str, limit: int = 100) -> list[dict]`
returning `[{"artist": str, "title": str, "mbid": str|None, "playcount": int}]`.

**This function does NOT exist yet** — add it to lastfm.py using the existing `_api_get()`
infrastructure (rate limiter + error handling already built). API call:
`tag.getTopTracks` with params `{"tag": tag, "limit": limit}`.

**`_load_cache()` must be updated** — currently initializes `{"artists": {}, "tracks": {}}` only.
Add `"tag_charts": {}` so chart results have a home in the cache:
```python
return {"artists": {}, "tracks": {}, "tag_charts": {}}
```
Cache key: `"tag_charts": {"heartbreak": [{"artist":..., "title":..., "playcount":...}], ...}`
TTL: tag chart cache entries are stable — store with the mining cache's 30-day TTL (in
`.mining_cache.json`), NOT in lastfm_cache.json (which has no TTL).

Mood → Last.fm tag mapping lives in `data/mood_lastfm_tags.json`:
```json
{
  "Heartbreak":        ["heartbreak", "breakup", "bitter breakup"],
  "Late Night Drive":  ["late night", "night drive", "driving at night"],
  "Hollow":            ["sad", "melancholic", "depression"],
  ...
}
```

For abstract moods with no direct Last.fm tag equivalent (e.g., "Liminal", "Smoke & Mirrors"):
map to the closest emotional territory tags and accept lower match rate. These moods
will rely more on anchor tracks and lyrics signals.

**track_context schema (required for `combine_expected_tags` feedback loop):**
`mood_observed_tag_weights(track_context, mood_name)` expects this exact format:
```python
track_context = {
    "<spotify_uri>": [
        {
            "mood": "Heartbreak",          # must match mood name exactly
            "tags": ["heartbreak", "sad"], # vocabulary tags for this mood
            "followers": 85000,            # authority weight; use Last.fm playcount
        }
    ]
}
```
For Last.fm-sourced mining: when a library track matches a tag chart result, populate
`track_context[uri]` with the matched mood, the Last.fm tag as vocabulary, and the
track's Last.fm playcount (from the `tag.getTopTracks` response field `playcount`) as
the follower proxy. Use `playcount` if available, else default to 10000.

**⚑ Intermediate validation gate:** After implementing M1.3, run a mini-scan before
proceeding to M1.4. Verify `.mining_cache.json` size > 50KB and `observed_mood_tags`
is non-empty. If the cache is still empty, the mining implementation has a bug that
must be fixed before continuing.

**Validation:** `mining_cache.json` size > 50KB. `observed_mood_tags` in snapshot is
non-empty. At least 20 moods have `mood_*` tags on library tracks.

---

### M1.4 — Mood Anchors

**What:**
Bundle `data/mood_anchors.json` — a set of anchor tracks per mood that serve as permanent
calibration points regardless of mining or API availability.

**Generation strategy — one-time development script + human review:**

`mood_anchors.json` is a **bundled static file** committed to the repo. It is generated
once by a developer-side script and then treated as curated data. It is NOT generated at
runtime during user scans.

**Step 1 — Run `scripts/generate_anchors.py` (create this script as part of M1.4):**
```python
# scripts/generate_anchors.py
# Reads data/mood_lastfm_tags.json, calls tag.getTopTracks for each mood's primary tag,
# writes top 25 results per mood to data/mood_anchors_candidates.json for review.
```
The script calls `lastfm.get_tag_top_tracks()` (implemented in M1.3) for each mood's
first tag in `mood_lastfm_tags.json`, takes top 25 results, and writes them to
`data/mood_anchors_candidates.json` as a review file.

**Step 2 — Human review of candidates:**
1. Take the top 25 returned tracks per mood as seed candidates
2. Deduplicate cross-mood (a track appearing in 3+ moods → reduce to the single most
   appropriate mood, remove from others)
3. Remove obvious mismatches
4. Add genre-diverse representatives Last.fm's chart missed (classical, jazz, non-English)
5. Write final reviewed set to `data/mood_anchors.json`

This reduces the work from ~2,610 fully hand-written entries to reviewing and pruning
~1,740 auto-generated candidates + filling ~30 gaps per under-served mood.

Format:
```json
{
  "Heartbreak": [
    { "artist": "Olivia Rodrigo",   "title": "drivers license" },
    { "artist": "Alanis Morissette","title": "You Oughta Know" },
    { "artist": "Lorde",            "title": "Liability" },
    ...
  ],
  ...
}
```

Coverage: all 87 moods × 10–20 tracks each (post-review).

Anchor matching runs in `core/scan_pipeline.py` after all enrichment, before scoring.
Zero-cost pass (no API calls, pure dict lookup). Any library track matching an anchor
(artist + title, case-insensitive, strip "feat." suffixes) gets `anchor_<moodname>: 1.0`.

Anchor match is the highest-confidence mood signal in the system.

**Validation:** At least 5 library tracks match anchors across at least 10 moods.

---

### M1.5 — Track Metadata Signals

**What:**
Add `_extract_metadata_signals(track: dict) -> dict[str, float]` in `core/enrich.py`.

Inputs (all from Spotify track object, already in snapshot):
- `name` (track title)
- `duration_ms`
- `explicit`
- `track_number`, `disc_number`, `album.total_tracks`
- `album.album_type` (single / album / compilation)
- `artists` (list — detect featuring artists)
- `album.name`

Outputs (tags added to `track_tags`):
```
meta_intro         → title matches "intro|opening|prelude" (0.6)
meta_outro         → title matches "outro|finale|end|closing" (0.6)
meta_interlude     → duration_ms < 90000 or title has "skit|interlude|reprise" (0.7)
meta_epic          → duration_ms > 480000 (0.5)
meta_explicit      → explicit == True (0.4) — boosts energy/raw/hype
meta_opener        → track_number == 1 and album_type == "album" (0.4)
meta_closer        → track_number == total_tracks and album_type == "album" (0.4)
meta_feature       → has feat. artist (0.3) — differentiates from solo tracks
meta_single        → album_type == "single" (0.3)
```

Title keyword extraction maps to mood clusters:
```
"midnight|3am|2am|night" → adds night:0.4
"morning|sunrise|dawn"   → adds morning:0.4
"love|heart|darling"     → adds love:0.3 (if not already tagged)
"rage|fury|war|fight"    → adds angry:0.3
"drive|road|highway|car" → adds drive:0.3
"rain|storm|cloud|grey"  → adds moody:0.3
```

This runs for 100% of library tracks, zero API calls, sub-second total.

**Validation:** Every track in `track_tags` has at least one `meta_*` key.

---

### M1.6 — Local Library Scan (AcoustID + Beets Integration)

**What:**
Wire the local library scan path end-to-end. `core/acoustid.py` already exists (239 lines)
but is completely orphaned — this milestone properly integrates it.

New UI button: **"Local Library Scan"** on `pages/2_Scan.py`.

**Path entry:** Pure `st.text_input` — Streamlit is a web application and cannot open
native OS file dialogs (tkinter.filedialog runs on the server, not the user's browser).
The user types or pastes their music root directory path. Show a clear placeholder like
`C:\Music` or `/home/user/Music`. Validate the path exists before proceeding.

Pipeline when local path is set:
1. Scan directory recursively for audio files (`.mp3`, `.flac`, `.aac`, `.ogg`, `.m4a`, `.wav`)
2. For each file: run `fpcalc` to get Chromaprint fingerprint (requires fpcalc binary)
3. POST fingerprint to AcoustID API → get MusicBrainz Recording ID (MBID)
4. Query MusicBrainz `recording/<mbid>?inc=tags+genres` → get per-recording tags
5. Match recording to Spotify track by (artist, title) → merge tags into `track_tags`
6. Also run beets integration if beets DB found (unchanged, already works)

Cache fingerprints permanently in `.acoustid_cache.json` — fingerprints never change.

Config (`config.py`) — these keys already exist; ensure they are documented and active:
- `LOCAL_MUSIC_PATH` — user's music root
- `FPCALC_PATH` — path to fpcalc binary (default: `fpcalc` on PATH)
- `ACOUSTID_API_KEY` — free registration at acoustid.org

If `fpcalc` not found: skip fingerprinting, show one-time notice with install instructions.
If `ACOUSTID_API_KEY` not set: skip MBID lookup, still run beets if available.

This path is gated — standard Spotify-only users never see it or wait for it.

**Validation:** With `LOCAL_MUSIC_PATH` set to a test directory containing 5 audio files,
`track_tags` receives MusicBrainz-sourced tags for matched tracks.

---

### M1.7 — Full Library Coverage: Lyrics + Last.fm Per-Track Tags

**What:**
Remove both enrichment caps that artificially limit per-track signal coverage:

**Cap 1 — Lyrics (`core/scan_pipeline.py`):**
Remove `min(600, int(350 * _enrich_mult))` from the lyrics max_tracks argument.
Replace with: fetch lyrics for all tracks, rate-limited at 0.25s/request.
Cache is permanent. On rescan, only uncached tracks are fetched.

**Cap 2 — Last.fm per-track tags (`core/scan_pipeline.py` lines 159–166):**
Currently: `_lf_cap = max(300, min(1000, len(all_tracks)))` — caps per-track Last.fm
lookup at 1,000 tracks. With a 2,612-track library, 1,612 tracks only get artist-level
tags at 55% weight. Replace with: `_lf_cap = len(all_tracks)` (no cap; cache prevents
re-fetching). The existing cache in `.lastfm_cache.json` makes rescans instant.

First-run messaging for both:
- "Fetching lyrics — [N] tracks, approx. [T] minutes. Cached permanently."
- "Fetching Last.fm track tags — [N] tracks. Cached permanently."

Show per-language breakdown in scan summary (already partially implemented).

**Validation:** After first scan, `.lyrics_cache.json` and `.lastfm_cache.json` contain
entries for all library tracks. Second scan skips all previously fetched tracks.
Last.fm track entries in cache ≈ library size.

---

### M1.8 — Scan UI Redesign

**What:**
Replace the current "Scan corpus" radio + "Re-scan Library" button with three distinct
scan modes:

#### Full Scan
Clears and re-runs mood scoring from scratch. Does NOT re-fetch API data that is cached.

Clears:
- `.last_scan_snapshot.json` (scoring results — always regenerated)

Respects TTL (re-fetches only if expired):
- `.mining_cache.json` — 30-day TTL. If expired, re-mines Last.fm tag charts before scoring.
  If not expired, reuses existing mining data. User can force re-mine via Custom Scan.

Keeps unconditionally (data does not change):
- `.lastfm_cache.json`
- `.deezer_cache.json`
- `.mb_cache.json`
- `.audiodb_cache.json`
- `.lyrics_cache.json`
- `.discogs_cache.json`
- `.acoustid_cache.json`
- `.spotify_genres_cache.json`

UI: One large primary button. Caption: "Re-scores your library using all cached enrichment
data. Re-fetches mood playlists if older than 30 days."

#### Custom Scan
Expander with checkboxes per enrichment source:
- [ ] Re-fetch Last.fm tags (clears lastfm_cache artist/track entries)
- [ ] Re-fetch Deezer data (clears deezer_cache track entries)
- [ ] Re-fetch AudioDB (clears audiodb_cache)
- [ ] Re-fetch MusicBrainz tags (clears mb_cache)
- [ ] Re-fetch lyrics (clears lyrics_cache — WARNING: slow)
- [ ] Re-mine mood playlists (clears mining_cache)
- [ ] Re-run scoring only (fastest, no API calls)

Each checkbox has a caption explaining what it does and how long it takes.

#### Local Library Scan
Path text input for music root directory (`st.text_input` — no OS file dialog).
Runs AcoustID fingerprinting on local files, merges with existing Spotify scan. Additive.

Shows: file count found, estimated fingerprinting time, fpcalc installation status.

**Layout:**
```
[  Full Scan  ]    [ Custom Scan ▼ ]    [ Local Library ]

  Last scan: 7 hours ago  ·  2,612 tracks  ·  79 moods
```

**Validation:** All three buttons exist and trigger distinct pipeline paths. Custom scan
checkboxes correctly gate which caches are cleared.

---

### M1.9 — User Playlist Mining Enhancement

**What:**
The code already mines owned playlists (`_mine_owned_playlists`). Improve it:

1. **Name matching:** Fuzzy match playlist name + description against all mood seed phrases
   (not just exact match). Use simple normalized Levenshtein or token overlap.
2. **Threshold:** Playlist name must achieve ≥ 0.6 match score against a mood.
3. **Description:** Also parse `playlist.description` field — often more descriptive.
4. **Weight:** Tracks from user's own playlists get `mood_<name>` tag at 0.9× weight
   (slightly below anchor match of 1.0×, but above Last.fm tag chart match of 0.75×).
5. **All playlists:** Fetch up to 200 playlists (currently capped at 48).

**Validation:** A playlist named "sad hours" or "2am drive" produces mood tags on its tracks.

---

## Phase 2 — Signal Expansion

**Goal:** Maximize per-track signal quality. Every track should have at least 3 independent
signal sources. No track should rely solely on artist-level inherited tags.

**Exit criteria:** lyr_* coverage ≥ 65% of library. Deezer BPM feeds audio proxy.
AudioDB fetches all available track data. MusicBrainz returns recording-level tags.

---

### M2.1 — NRC Emotion Lexicon Integration

**What:**
Bundle `data/nrc_emotions.json` — the NRC Word-Emotion Association Lexicon processed
to include only the emotionally significant words.

Source: NRC EmoLex by Saif M. Mohammad & Peter D. Turney (National Research Council Canada).
License: **Free for research/educational use. For public commercial deployment, written
permission from NRC is required.** If commercial licensing is a concern before go-live,
this bundled file can be replaced with an equivalent open-licensed resource (e.g., a subset
derived from WordNet Affect, which is MIT-compatible). The integration code does not change.

Processing: From the full 14,182-word lexicon, keep only words with at least one
emotion score > 0. Result: approximately 6,468 words. Stored as:
```json
{
  "abandon":    { "fear": 1, "sadness": 1 },
  "abhor":      { "anger": 1, "disgust": 1 },
  "cherish":    { "anticipation": 1, "joy": 1, "trust": 1 },
  ...
}
```
File size: ~280KB. Acceptable to bundle.

Emotion → lyr_* mapping (mapped to lyrics.py's 25 existing categories only):
```
anger       → lyr_angry
fear        → lyr_dark
sadness     → lyr_sad
joy         → lyr_euphoric          ← NOTE: lyr_happy does not exist; use lyr_euphoric
anticipation → lyr_hope
trust       → lyr_faith
disgust     → lyr_dark + lyr_angry (0.5× weight)
surprise    → no mapping (too ambiguous)
```

Integration in `core/lyrics.py`: after keyword matching, run NRC word lookup on
tokenized lyrics. NRC words are weighted at 0.4× vs keyword matches at 1.0×.

No new pip dependencies. Pure JSON lookup.

**Validation:** lyr_* tags appear on tracks whose lyrics contain NRC emotion words
but do not contain the explicit keyword list entries.

---

### M2.2 — VADER Valence Integration

**What:**
Replace the AFINN approach with **VADER** (Valence Aware Dictionary and sEntiment Reasoner).

VADER advantages over AFINN:
- MIT licensed (no commercial restriction)
- 7,500+ lexicon entries vs AFINN's 2,477
- Handles capitalization, punctuation emphasis, slang, and negation
- Returns compound score [-1.0, +1.0] plus positive/negative/neutral ratios
- Specifically designed for short social text (matches lyric style better than AFINN)

Add `vaderSentiment` to `requirements.txt`. No data file needed — model is bundled with pip.

**Integration path — VADER result flows through track_tags into audio_proxy:**

`audio_proxy.py` receives `(track, artist_genres_map, track_tags)` — no direct lyrics access.
The path is:

1. In `core/lyrics.py`, after computing mood keyword scores for a track, run VADER on the
   full lyric text. Store the compound score as a numeric tag:
   ```python
   track_tags[uri]["vader_valence"] = (compound + 1.0) / 2.0  # map [-1,1] → [0,1]
   ```

2. In `core/audio_proxy.py`, `build_proxy_feature_dict()` reads `track_tags` already.
   Add: if `track_tags.get(uri, {}).get("vader_valence") is not None`, blend it into
   the proxy valence dimension at **12% weight**:
   ```python
   proxy_valence = 0.88 * heuristic_valence + 0.12 * track_tags[uri]["vader_valence"]
   ```

This gives the audio proxy a real lyric-derived valence anchor instead of pure genre heuristics.
The 12% is conservative — tune upward after validation scan if valence variance improves.

**Validation:** Two tracks by the same artist — one with clearly positive lyrics, one
with clearly negative — produce different valence values in their proxy audio vectors.

---

### M2.3 — Expanded MOOD_KEYWORDS

**What:**
Expand `MOOD_KEYWORDS` in `core/lyrics.py` from ~100 to ~400–500 entries per mood,
using NRC-informed synonyms, common phrases, and slang.

Expansion strategy per mood:
1. Start with existing keywords
2. Add all NRC words that map to the mood's emotion category
3. Add common phrase patterns ("can't sleep", "miss you", "nothing left", "on top of the world")
4. Add cross-language expansions (Spanish, French, German, Portuguese, Italian, Dutch already
   present — expand keyword count in each)
5. Add contemporary slang where stable ("L", "no cap", "mid" etc. only if clearly mood-relevant)

Priority moods to expand first (currently weakest signal):
- Hollow (introspective, empty, dissociative)
- Liminal (between states, transitional)
- 3 AM Unsent Texts (late night overthinking)
- Overthinking (anxious rumination)
- Smoke & Mirrors (deceptive, illusory)

**Validation:** lyr_* coverage increases from 30% to ≥ 65% of library.

---

### M2.4 — AudioDB: Remove Track Cap

**What:**
In `core/audiodb.py`, remove the `max_tracks=100` limit on per-track mood data fetching.

AudioDB's free API returns `strMood`, `strTheme`, `strStyle` per individual track.
For artists with 30–50 tracks in the library, the 100-track cap means some are fetched
and some aren't — inconsistent coverage. Remove the cap entirely.

At 0.3s/request and ~95% cache hits on rescan: negligible time cost.

**Validation:** All Linkin Park tracks (53 in library) have AudioDB track-level data,
not just the first 100 alphabetically.

---

### M2.5 — MusicBrainz Recording Tags

**What:**
Upgrade `core/musicbrainz.py` recording lookups to include `inc=tags+genres`.

Currently: MusicBrainz is used for coverage gap-fill, fetching artist/release data.
The recording endpoint (`/recording/<mbid>?inc=tags+genres`) returns community-tagged
mood and genre terms at the individual track level — separate from artist/release level.

Add extraction of recording tags to the existing MusicBrainz enrichment pass.
Map recording tags to `track_tags` using the existing tag normalization logic.

If MBID not known (most tracks): attempt lookup via
`recording/?query=artist:"X" AND recording:"Y"` — MusicBrainz's search API.

**Validation:** Tracks with MusicBrainz MBIDs receive recording-level mood tags
distinct from their artist-level tags.

---

### M2.6 — Deezer BPM into Audio Proxy

**What:**
Feed the Deezer BPM data (from M1.2) into `core/audio_proxy.py`.

Currently: `tempo_norm` is a heuristic based on genre keywords (e.g., "metal" → 0.65 tempo band).
With real BPM data: `tempo_norm = (bpm - 60) / (200 - 60)` clamped to [0, 1].

Priority: Deezer BPM > heuristic estimate. If BPM is None, fall back to keyword heuristic.

Also use BPM to refine energy estimate:
- BPM > 160 → energy += 0.08
- BPM < 75  → energy -= 0.08

Use contributor count from Deezer (feat. artists) to inform danceability slightly
(more contributors → slightly higher danceability, typical of club/hip-hop tracks).

**Validation:** Two tracks by the same artist with different BPM values from Deezer
produce different `tempo_norm` values in their proxy audio vectors.

---

### M2.7 — Last.fm getSimilar Mood Inference

**What:**
For tracks with signal confidence below 0.4 (no lyr_*, no anchor match, no mood_* tags),
run `track.getSimilar(artist, title, limit=5)` on Last.fm.

The 5 returned similar tracks are looked up in the library. If those similar tracks have
existing mood tags (from any source), infer the uncovered track's moods from them:
- For each similar track, take its top-scoring mood
- Aggregate: if 3/5 are tagged Hollow, add `inferred_hollow: 0.4`

This is a graph-based fallback — works well for mid-popularity tracks that Last.fm knows
about but aren't tagged enough to have direct mood data.

Run as a post-enrichment pass, only for tracks with zero per-track mood signal.
Cache similar track results in `lastfm_cache.json` under `"similar"` key.

**Validation:** At least 10% of previously-zero-signal tracks receive inferred mood tags.

---

## Phase 3 — Scoring Architecture

**Goal:** The accumulated per-track signals from Phase 1+2 must be reflected in scoring.
Artist-level fallback tags must not override per-track data.

**Exit criteria:** std ≥ 0.05 for ≥ 60% of moods. Validation scan passes all checks.

---

### M3.1 — Per-Track Signal Confidence in Scorer

**What:**
Add a `_signal_confidence(uri, track_tags, profiles)` function in `core/scorer.py`.

Logic:
- Track has lyr_* tags → per-track confidence += 0.35
- Track has bpm_* or meta_* tags → += 0.20
- Track has mood_* or anchor_* tags → += 0.45
- Track has MusicBrainz recording tags → += 0.20
- Sum > 1.0 → cap at 1.0

In `tag_score()`: multiply each active_tag's weight by:
- `1.0` if the tag is per-track (lyr_*, bpm_*, meta_*, mood_*, anchor_*)
- `max(0.7, 1.0 - confidence)` if the tag is artist-level and per-track data already exists

Effect: for Eminem tracks with lyr_family and lyr_hype tags, those dominate. The artist-level
"angry" tag is downweighted proportionally to how much per-track data already exists.

**Validation:** Two Eminem tracks (one with lyr_sad, one with lyr_hype) score differently
in at least 3 mood comparisons.

---

### M3.2 — Score Spread Fix

**What:**
The current `effective_denom = min(len(expected_tags), 8)` in `tag_score()` compresses
variance.

**Fix:** Replace the static cap with a proportional formula:
```python
effective_denom = max(3, len(expected_tags) // 3)
```
This scales denominator with mood complexity — a mood with 6 expected tags uses denom=3,
a mood with 27 expected tags uses denom=9. No pre-scoring pass required, no chicken-and-egg.

The formula can be tuned per mood after the validation scan:
- If a mood's top scores are too clustered → increase `// 3` to `// 4`
- If too sparse → decrease to `// 2`

Also: adjust the `ensure_minimum` backfill floor from `min_score * 0.7` to `min_score * 0.5`
to allow more backfill candidates while maintaining the re-enforcement of artist diversity
after backfill (already in place).

**Validation:** std distribution improves. Run analysis script on new scan:
`python3 -c "..."` (see validation checklist below).

---

### M3.3 — Weight Recalibration

**What:**
With real per-track BPM (tempo dimension now real, not heuristic), the audio proxy
becomes more reliable. Adjust:

```
W_TAGS           = 0.44   (from 0.46 — slightly reduced)
W_SEMANTIC       = 0.24   (from 0.26 — slightly reduced)
W_GENRE          = 0.18   (unchanged)
W_METADATA_AUDIO = 0.14   (from 0.10 — increased now BPM is real)
```

These are starting values. After the validation scan, tune based on observed std distribution
and mood quality inspection.

**Validation:** Scan runs without error. Mood quality inspection (see below) passes.

---

### M3.4 — Validation Scan + Quality Gates

**What:**
Run a full scan and execute the validation checklist:

```python
# validation_check.py — run after each milestone
checks = [
  ("Mining cache non-empty",          lambda s: len(s['mining_cache'].get('track_tags',{})) > 100),
  ("Deezer BPM coverage >= 50%",      lambda s: bpm_coverage(s) >= 0.50),
  ("lyr_* coverage >= 65%",           lambda s: lyr_coverage(s) >= 0.65),
  ("Artist cap enforced",             lambda s: max_artist_repeat(s) <= 3),
  ("Score std >= 0.05 for 60% moods", lambda s: passing_std_fraction(s) >= 0.60),
  (">= 65 moods populated",           lambda s: populated_moods(s) >= 65),
  ("No mood is single-artist",        lambda s: no_single_artist_mood(s)),
  ("Heartbreak != Villain Arc",       lambda s: mood_overlap(s, 'Heartbreak', 'Villain Arc') < 0.4),
]
```

Also: manual inspection of 10 specific moods:
- Heartbreak, Hollow, Late Night Drive, Villain Arc, Overflow, Healing Kind, Deep Focus,
  Nostalgia, Hard Reset, Liminal

For each: top 10 tracks listed, artist distribution checked, mood coherence assessed.

---

## Cache Persistence Rules

| Cache file | Cleared by Full Scan | Cleared by Custom | TTL | Notes |
|---|---|---|---|---|
| `.mining_cache.json` | TTL only (30d) | Optional | 30 days | Auto-refreshes when expired |
| `.last_scan_snapshot.json` | YES | YES | None | Scoring output |
| `.lastfm_cache.json` | NO | Optional | None | Tags don't change |
| `.deezer_cache.json` | NO | Optional | None | BPM doesn't change |
| `.audiodb_cache.json` | NO | Optional | None | Editorial data stable |
| `.mb_cache.json` | NO | Optional | None | Recording tags stable |
| `.lyrics_cache.json` | NO | Optional | None | Lyrics don't change |
| `.discogs_cache.json` | NO | Optional | None | Genre data stable |
| `.acoustid_cache.json` | NO | Optional | None | Fingerprints never change |
| `.spotify_genres_cache.json` | NO | Optional | None | Genre data stable |

**Rule:** If the underlying real-world data does not change, the cache is never cleared
automatically. The user must explicitly request it via Custom Scan. Full Scan only clears
the mood scoring output. Mining cache is TTL-driven (30 days) — Full Scan triggers
re-mining only when the cache has expired, not unconditionally.

---

## Data Files to Bundle

| File | Source | Size | License |
|---|---|---|---|
| `data/nrc_emotions.json` | NRC EmoLex (Mohammad & Turney, NRC Canada) | ~280KB | Free research/educational; confirm for commercial |
| `data/mood_anchors.json` | Last.fm-seeded + hand-reviewed | ~120KB | Original |
| `data/mood_lastfm_tags.json` | Hand-curated | ~12KB | Original |

**No AFINN file** — replaced by VADER pip package (MIT licensed, no bundle needed).

Total new data: ~412KB. Acceptable to bundle in repository.

Note on NRC license: before pushing public, confirm with NRC or replace the bundled
file with a WordNet Affect subset. The integration code in lyrics.py does not change
regardless of which emotion lexicon backs the JSON.

---

## Session Plan

| Session | Milestones | Primary files changed |
|---|---|---|
| **Session 1A** | M1.0, M1.1, M1.2, M1.3, M1.4 | packs.json, deezer.py, playlist_mining.py, lastfm.py, data/, config.py |
| **Session 1B** | M1.5, M1.6, M1.7, M1.8, M1.9 | enrich.py, acoustid.py, scan_pipeline.py, pages/2_Scan.py, lyrics.py |
| **Session 2** | M2.1 → M2.7 | lyrics.py, audio_proxy.py, musicbrainz.py, audiodb.py, requirements.txt |
| **Session 3** | M3.1 → M3.4 | scorer.py, scan_pipeline.py, config.py, validation script |
| **Session 4** | Validation passthrough, quality inspection, bug fixes | All |

**Token budget per session:** ~150K–180K tokens
**Total estimated:** ~700K–800K tokens across 4-5 sessions (split of Session 1 adds ~100K)
**Go-live gate:** User is satisfied with playlist quality on their actual library

---

## Go-Live Checklist

Before pushing public:

- [ ] All M1–M3 milestones validated
- [ ] packs.json audit complete — no cross-contaminating expected_tags
- [ ] Validation scan passes all automated checks
- [ ] Manual inspection of 10 moods passes
- [ ] No single-artist mood in any scan result
- [ ] First scan UX: progress messages are clear, times are stated
- [ ] Rescan is fast (< 30s excluding mood scoring)
- [ ] All three scan modes work (Full, Custom, Local)
- [ ] Connect page shows all services (fixed)
- [ ] Taste Map ocean bug is fixed (done)
- [ ] All tests pass (`pytest tests/`)
- [ ] NRC license verified OR replaced with open-licensed alternative
- [ ] VADER added to requirements.txt and confirmed in production
- [ ] README updated to reflect new data sources and scan modes
- [ ] `.env.example` updated with new config keys
- [ ] `SETUP.md` updated with fpcalc installation instructions

---

*Document version: 1.4 — Full source verification complete. All files read. Final.*
*v1.0→v1.1: M1.1/M1.6 contradiction, tkinter, effective_denom, AFINN→VADER, lyr_happy,*
*NRC license, Deezer non-English, anchor auto-gen, Session 1 split, packs cleanup to M1.0.*
*v1.1→v1.2: W_AUDIO not deleted but renamed; audio_groups/recommend/profile excluded from*
*M1.1; mining TTL 7→30 days; Full Scan respects TTL.*
*v1.2→v1.3: effective_score_weights already handles proxy (M1.1 is cleanup only);*
*scan_pipeline 0.0 literals → cfg.W_METADATA_AUDIO; track_context schema specified;*
*VADER integration path specified; anchor generation script specified.*
*v1.3→v1.4: packs.json full audit — 63 over-broad tags found, specific removals listed,*
*M1.0 re-scoped to ~3hr audit (was 30min); deezer._load_cache needs tracks key (M1.2);*
*lastfm._load_cache needs tag_charts key + get_tag_top_tracks doesn't exist yet (M1.3);*
*passes_hard_filters already skips proxy tracks — no change needed; config verified;*
*M1.7 expanded to also remove Last.fm per-track cap (was only lyrics cap).*
