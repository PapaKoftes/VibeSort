# Vibesort — Signal System Rebuild Plan

**Status:** In progress
**Target:** Fully working per-track signal system for any public user
**Milestone count:** 3 phases, 11 milestones, 1 final validation gate

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

7. **Respect caches across rescans.** Enrichment data that does not change (Last.fm tags,
   Deezer BPM, AudioDB moods, lyrics, MusicBrainz tags) shall never be re-fetched unless the
   user explicitly requests it. Only mood scoring (the final pipeline stage) re-runs on rescan.

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
  ├── lyr_*            → mood tags from lyrics × NRC Emotion Lexicon × AFINN valence
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
  └── audio_score      → proxy vector (BPM-anchored tempo, AFINN-informed valence)

OUTPUT
  └── mood_results     → ranked playlists, 20-50 tracks, max 3 per artist, std ≥ 0.05 target
```

---

## Phase 1 — Foundation

**Goal:** Remove everything dead, restore the human-curated mood signal, maximize per-track data
acquisition, redesign scan UX.

**Exit criteria:** A scan produces visibly different results per mood. Heartbreak does not consist
of only one artist. Mining cache is non-empty.

---

### M1.1 — Remove Dead Code and Dead Config

**What:**
- Delete `core/acoustid.py` (239 lines, never called; local library path will use a new
  integrated approach instead of this orphan)
- Remove `enrich.audio_features()` call from `core/enrich.py` — the Spotify `/audio-features`
  endpoint returns 403 permanently. Replace with a one-line stub `return {}`.
- Remove from `config.py`: `W_AUDIO`, `ACOUSTID_API_KEY`, `FPCALC_PATH`, `LOCAL_MUSIC_PATH`
  (these controlled the dead signal only)
- Remove AcoustID UI section from `pages/9_Settings.py`
- Remove `W_AUDIO` branch from weight logic in `core/scan_pipeline.py`

**What to keep:**
- `core/rym.py` — active when user provides CSV export, works correctly
- `core/beets.py` — active when beets DB found, wired correctly
- The `audio_features_map` variable in the pipeline can remain as empty dict with no special handling

**Validation:** `grep -r "acoustid\|W_AUDIO\|FPCALC" core/ config.py` returns zero results.

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

Then add `get_artist_top_tracks(artist_name: str, limit: int = 50) -> list[dict]` using
`/search?q=artist:"<name>"&limit=50` as a bulk approach for artists with many library tracks.

Cache structure in `.deezer_cache.json`:
```json
{
  "artists": { "<artist_lower>": ["Genre1", "Genre2"] },
  "tracks":  { "<artist_lower>|||<title_lower>": { "bpm": 128, "explicit": true, "rank": 847000 } }
}
```

Rate: keep 150ms gap. Tracks cached permanently (BPM doesn't change).

First-run messaging: "Fetching per-track audio data from Deezer — this runs once and is cached
permanently. Approx. [N] seconds for your library."

**Validation:** `.deezer_cache.json` has a `"tracks"` key with entries. BPM is non-null for
> 50% of mainstream artists.

---

### M1.3 — Last.fm Tag Charts as Mood Ground Truth

**What:**
Replace the dead Spotify public playlist mining path with Last.fm `tag.getTopTracks`.

Last.fm's API: `tag.getTopTracks(tag="heartbreak", limit=100)` returns the 100 tracks
the community has most associated with that tag. This is exactly what Spotify playlist mining
was doing — finding tracks humans labelled with a mood — but via Last.fm's tagging system
instead of named playlists.

Implementation in `core/playlist_mining.py`:
1. For each mood, map its `seed_phrases` to Last.fm tag vocabulary
   (e.g., "heartbreak playlist" → tags: ["heartbreak", "breakup", "sad breakup"])
2. Call `tag.getTopTracks` for each tag (up to 3 per mood, limit=100 each)
3. Deduplicate, normalize (artist+title → lowercase)
4. Cross-reference against the user's library: any library track matching a returned
   artist+title gets a `mood_<moodname>` tag added to `track_tags`
5. Tracks not in library but returned → stored as `track_context` for semantic reference
6. Cache in `.mining_cache.json` with 30-day TTL (Last.fm tag charts are stable)

Also implement `lastfm.py:get_tag_top_tracks(tag: str, limit: int = 100) -> list[dict]`
returning `[{"artist": str, "title": str, "mbid": str|None}]`.

Mood → Last.fm tag mapping lives in `data/mood_lastfm_tags.json`:
```json
{
  "Heartbreak":        ["heartbreak", "breakup", "bitter breakup"],
  "Late Night Drive":  ["late night", "night drive", "driving at night"],
  "Hollow":            ["sad", "melancholic", "depression"],
  ...
}
```

**Validation:** `mining_cache.json` size > 50KB. `observed_mood_tags` in snapshot is
non-empty. At least 20 moods have `mood_*` tags on library tracks.

---

### M1.4 — Mood Anchors

**What:**
Bundle `data/mood_anchors.json` — a curated set of anchor tracks per mood that serve as
permanent calibration points regardless of mining or API availability.

Format:
```json
{
  "Heartbreak": [
    { "artist": "Olivia Rodrigo",  "title": "good 4 u" },
    { "artist": "Alanis Morissette", "title": "You Oughta Know" },
    { "artist": "Taylor Swift",    "title": "Picture To Burn" },
    { "artist": "Paramore",        "title": "Misery Business" },
    { "artist": "Eminem",          "title": "Kim" },
    { "artist": "Lorde",           "title": "Liability" },
    ...
  ],
  ...
}
```

Coverage: all 87 moods × 15–30 tracks each. Tracks are universally agreed-upon
representatives of the mood, spanning genres so the anchor set is broad.

Any library track matching an anchor (artist + title, case-insensitive) gets
`anchor_<moodname>: 1.0` added to its tags. Anchor match is the highest-confidence
mood signal in the system.

Anchor matching runs in `core/scan_pipeline.py` after all enrichment, before scoring.
It is a zero-cost pass (no API calls, pure dict lookup).

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
Wire the local library scan path end-to-end.

New UI button: **"Local Library Scan"** on `pages/2_Scan.py` opens a directory picker
(via `st.text_input` with a Browse button using `tkinter.filedialog` on desktop, or manual
path entry on web). User picks their music root directory.

Pipeline when local path is set:
1. Scan directory recursively for audio files (`.mp3`, `.flac`, `.aac`, `.ogg`, `.m4a`, `.wav`)
2. For each file: run `fpcalc` to get Chromaprint fingerprint (requires fpcalc binary)
3. POST fingerprint to AcoustID API → get MusicBrainz Recording ID (MBID)
4. Query MusicBrainz `recording/<mbid>?inc=tags+genres` → get per-recording tags
5. Match recording to Spotify track by (artist, title) → merge tags into `track_tags`
6. Also run beets integration if beets DB found (unchanged, already works)

Cache fingerprints permanently in `.acoustid_cache.json` — fingerprints never change.

Config:
- `LOCAL_MUSIC_PATH` restored but now actually used
- `FPCALC_PATH` restored and documented
- `ACOUSTID_API_KEY` restored (free registration at acoustid.org)

If `fpcalc` not found: skip fingerprinting, show user a one-time notice with install instructions.
If `ACOUSTID_API_KEY` not set: skip MBID lookup, still run beets if available.

This entire path is gated — standard Spotify-only users never see it or wait for it.

**Validation:** With `LOCAL_MUSIC_PATH` set to a test directory containing 5 audio files,
`track_tags` receives MusicBrainz-sourced tags for matched tracks.

---

### M1.7 — Lyrics: Full Library Coverage

**What:**
Remove the `min(600, int(350 * _enrich_mult))` cap from the lyrics enrichment call
in `core/scan_pipeline.py`.

Replace with: fetch lyrics for all tracks, rate-limited at 0.25s/request.
Cache is permanent (lyrics don't change). On rescan, only uncached tracks are fetched.

First-run messaging: "Fetching lyrics — [N] tracks, approx. [T] minutes. This runs
once and is cached permanently. Future scans are instant."

Show per-language breakdown in scan summary (already partially implemented).

**Validation:** After first scan, `.lyrics_cache.json` size grows proportionally to
library size. Second scan skips all previously fetched tracks.

---

### M1.8 — Scan UI Redesign

**What:**
Replace the current "Scan corpus" radio + "Re-scan Library" button with three distinct
scan modes:

#### Full Scan
Clears and re-runs mood scoring from scratch. Does NOT re-fetch API data that is cached.

Clears:
- `.mining_cache.json` (mood ground truth — re-mines from Last.fm)
- `.last_scan_snapshot.json` (scoring results)

Keeps (these don't change when you rescan):
- `.lastfm_cache.json`
- `.deezer_cache.json`
- `.mb_cache.json`
- `.audiodb_cache.json`
- `.lyrics_cache.json`
- `.discogs_cache.json`
- `.acoustid_cache.json`
- `.spotify_genres_cache.json`

UI: One large primary button. Caption explains what gets cleared and why.

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
Opens a path input for music root directory. Runs AcoustID fingerprinting on local files,
merges with existing Spotify scan. Does not replace it — additive.

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
License: Free for research/non-commercial. Download from saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm

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

Emotion → lyr_* mapping:
```
anger       → lyr_angry
fear        → lyr_dark
sadness     → lyr_sad
joy         → lyr_euphoric + lyr_happy
anticipation → lyr_hope
trust       → lyr_faith
disgust     → lyr_dark + lyr_angry (0.5× weight)
surprise    → no direct mapping (too ambiguous)
```

Integration in `core/lyrics.py`: after keyword matching, run NRC word lookup on
tokenized lyrics. Any NRC word found adds to the corresponding lyr_* score.
NRC words are weighted at 0.4× vs keyword matches at 1.0× (keywords are more specific).

No new pip dependencies. Pure JSON lookup.

**Validation:** lyr_* tags appear on tracks whose lyrics contain NRC emotion words
but do not contain the explicit keyword list entries.

---

### M2.2 — AFINN Valence Integration

**What:**
Bundle `data/afinn.json` — AFINN-111 sentiment lexicon by Finn Årup Nielsen.
License: Open Database License (ODbL). 2,477 words rated -5 (most negative) to +5 (most positive).

Format:
```json
{ "abandon": -2, "awesome": 4, "love": 3, "hate": -3, "murder": -2, ... }
```
File size: ~28KB.

Use in `core/audio_proxy.py`: after computing the heuristic energy/valence vector,
if the track has lyrics cached, run AFINN on the lyric text and compute mean valence score.
Map [-5, +5] → [0.0, 1.0]. Blend at 30% weight into the proxy valence dimension.

This gives the audio proxy a real lyric-derived valence anchor instead of pure genre heuristics.

**Validation:** Two tracks by the same artist — one with positive lyrics, one with negative —
produce different valence values in their proxy audio vectors.

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

If MBID not known (most tracks): attempt lookup by `recording/?query=artist:"X" AND recording:"Y"`
— MusicBrainz's search API.

**Validation:** Tracks with MusicBrainz MBIDs receive recording-level mood tags
distinct from their artist-level tags.

---

### M2.6 — Deezer BPM into Audio Proxy

**What:**
Feed the Deezer BPM data (from M1.2) into `core/audio_proxy.py`.

Currently: `tempo_norm` is a heuristic based on genre keywords (e.g., "metal" → 0.65 tempo band).
With real BPM data: `tempo_norm = (bpm - 60) / (200 - 60)` clamped to [0, 1].

Priority: Deezer BPM > heuristic estimate. If BPM is None (Deezer returned no data), fall back
to existing keyword heuristic.

Also use BPM to refine energy estimate:
- BPM > 160 → energy += 0.08
- BPM < 75  → energy -= 0.08

Use contributor count from Deezer (feat. artists) to inform danceability slightly
(more contributors → slightly higher danceability, typical of club/hip-hop tracks).

**Validation:** Two Eminem tracks with different BPM values from Deezer produce
different `tempo_norm` values in their proxy audio vectors.

---

### M2.7 — Last.fm getSimilar Mood Inference

**What:**
For tracks with confidence below 0.4 (no lyr_* tags, no anchor match, no mood_* tags),
run `track.getSimilar(artist, title, limit=5)` on Last.fm.

The 5 returned similar tracks are looked up in the library. If those similar tracks have
existing mood tags (from any source), infer the uncovered track's moods from them:
- For each similar track, take its top-scoring mood
- Aggregate across 5 similar tracks: if 3/5 are tagged Hollow, add `inferred_hollow: 0.4`

This is a graph-based fallback — works well for mid-popularity tracks that Last.fm knows
about but aren't tagged enough to have direct mood data.

Run as a post-enrichment pass, only for tracks with zero per-track mood signal.
Cache: store similar track results in `lastfm_cache.json` under `"similar"` key.

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
- `max(0.7, 1.0 - confidence)` if the tag is artist-level and the track already has per-track data

Effect: for Eminem tracks with lyr_family and lyr_hype tags, those dominate. The artist-level
"angry" tag is downweighted proportionally to how much per-track data already exists.

**Validation:** Two Eminem tracks (one with lyr_sad, one with lyr_hype) score differently
in at least 3 mood comparisons.

---

### M3.2 — Score Spread Fix

**What:**
The current `effective_denom = min(len(expected_tags), 8)` in `tag_score()` compresses
variance. A mood with 27 expected tags uses denominator 8. A track hitting 4 tags scores
0.5, one hitting 6 scores 0.75 — but the ACTUAL difference between candidates is smaller
because most tracks hit 1–3 tags regardless.

Fix: compute `effective_denom` dynamically based on the 80th percentile of tags-hit
across all scored tracks for this mood (computed once per mood, cached). This ensures
the denominator reflects what's achievable in practice, not a static cap.

Also: adjust the `ensure_minimum` backfill floor from `min_score * 0.7` to `min_score * 0.5`
to allow more backfill candidates while maintaining the 2× re-enforcement of artist diversity
after backfill (already in place from the previous fix).

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
  ("Deezer BPM coverage ≥ 50%",      lambda s: bpm_coverage(s) >= 0.50),
  ("lyr_* coverage ≥ 65%",           lambda s: lyr_coverage(s) >= 0.65),
  ("Artist cap enforced",             lambda s: max_artist_repeat(s) <= 3),
  ("Score std ≥ 0.05 for 60% moods", lambda s: passing_std_fraction(s) >= 0.60),
  ("≥ 65 moods populated",           lambda s: populated_moods(s) >= 65),
  ("No mood is single-artist",        lambda s: no_single_artist_mood(s)),
  ("Heartbreak ≠ Villain Arc",       lambda s: mood_overlap(s, 'Heartbreak', 'Villain Arc') < 0.4),
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
| `.mining_cache.json` | YES | Optional | 30 days | Re-mined from Last.fm |
| `.last_scan_snapshot.json` | YES | YES | None | Scoring output |
| `.lastfm_cache.json` | NO | Optional | None | Tags don't change |
| `.deezer_cache.json` | NO | Optional | None | BPM doesn't change |
| `.audiodb_cache.json` | NO | Optional | None | Editorial data stable |
| `.mb_cache.json` | NO | Optional | None | Recording tags stable |
| `.lyrics_cache.json` | NO | Optional | None | Lyrics don't change |
| `.discogs_cache.json` | NO | Optional | None | Genre data stable |
| `.acoustid_cache.json` | NO | Optional | None | Fingerprints never change |
| `.spotify_genres_cache.json` | NO | Optional | None | Genre data stable |

**Rule:** If the underlying real-world data does not change (lyrics, BPM, genre tags, audio
fingerprints), the cache is never cleared automatically. The user must explicitly request it
via Custom Scan. Full Scan only clears the mood scoring output and the mining ground truth.

---

## Data Files to Bundle

| File | Source | Size | License |
|---|---|---|---|
| `data/nrc_emotions.json` | NRC EmoLex (Mohammad & Turney, NRC Canada) | ~280KB | Free non-commercial |
| `data/afinn.json` | AFINN-111 (Finn Årup Nielsen) | ~28KB | ODbL (open) |
| `data/mood_anchors.json` | Hand-curated | ~180KB | Original |
| `data/mood_lastfm_tags.json` | Hand-curated | ~12KB | Original |

Total new data: ~500KB. Acceptable to bundle in repository.

---

## Session Plan

| Session | Milestones | Primary files changed |
|---|---|---|
| **Session 1** | M1.1 → M1.9 | deezer.py, playlist_mining.py, lastfm.py, scan_pipeline.py, enrich.py, pages/2_Scan.py, config.py, data/ |
| **Session 2** | M2.1 → M2.7 | lyrics.py, audio_proxy.py, musicbrainz.py, audiodb.py, scorer.py (read-only in this session) |
| **Session 3** | M3.1 → M3.4 | scorer.py, scan_pipeline.py, config.py, validation script |
| **Session 4** | Validation passthrough, quality inspection, bug fixes | All |

**Token budget per session:** ~150K–180K tokens
**Total estimated:** ~600K–700K tokens across 4 sessions
**Go-live gate:** User is satisfied with playlist quality on their actual library

---

## Go-Live Checklist

Before pushing public:

- [ ] All M1–M3 milestones validated
- [ ] Validation scan passes all automated checks
- [ ] Manual inspection of 10 moods passes
- [ ] No single-artist mood in any scan result
- [ ] First scan UX: progress messages are clear, times are stated
- [ ] Rescan is fast (< 30s excluding mood scoring)
- [ ] All three scan modes work (Full, Custom, Local)
- [ ] Connect page shows all services (fixed)
- [ ] Taste Map ocean bug is fixed (done)
- [ ] All tests pass (`pytest tests/`)
- [ ] README updated to reflect new data sources and scan modes
- [ ] `.env.example` updated with new config keys
- [ ] `SETUP.md` updated with fpcalc installation instructions

---

*Document version: 1.0 — Written pre-implementation. Update milestone status as work progresses.*
