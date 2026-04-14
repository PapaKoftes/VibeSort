# Vibesort — Full Roadmap to Public Release

> **Status:** Beta (private, friend-tested). Target: public GitHub release.  
> **Core philosophy:** Human curation is the product. Every technical decision serves the goal of making the right song land in the right mood. The algorithm is infrastructure. The taste is the soul.

---

## Where we are right now

**What works well:**
- 87 mood definitions with semantic cores, audio targets, forbidden signals, genre constraints
- 546 human-curated anchor tracks (6.3 avg per mood) — the strongest signal we have
- Multi-signal scoring: tags × semantic × genre × audio proxy
- Graph propagation via Last.fm similarity — finds tracks adjacent to anchors
- Cohesion filtering — playlists that don't feel random
- Staging shelf → batch deploy to Spotify
- Portable Windows zip (128 MB, zero-install for friends)
- Desktop shortcut + Mac `.command` launcher

**What's genuinely broken or weak:**
- `mining_blocked=True` in Dev Mode — playlist item reads are blocked, so the main enrichment path is dead
- Audio vectors are `[0.5]*6` for ~95% of tracks (Spotify deprecated audio features Nov 2024) — cohesion scores are inflated/meaningless on this axis
- 73% track coverage pre-fix (only 27% of library assigned to any mood) — partly fixed by `_MAX_PL` 3→4, but root cause is thin signal
- No real semantic matching — "semantic_score" is token overlap, not actual meaning similarity
- Last.fm, ListenBrainz, Apple Music: wired up partially, not in-app connectable without `.env` editing
- No public GitHub release, no installer, no automated portable build

---

## The signal chain: honest picture

```
Current active signals (with mining_blocked + no Spotify audio):

  Deezer       ████░░░░░░  BPM only. Energy/loudness fields exist but unused.
  MusicBrainz  ████░░░░░░  Genre tags. Sparse coverage (~40% of tracks).
  Lyrics NLP   ██████░░░░  Sentiment buckets (lyr_sad, lyr_dark etc). Noisy but real.
  Anchors      ██████████  Human curation. The only true mood signal. Everything else feeds into this.
  Last.fm sim  ████████░░  Graph propagation from anchors. Strong when Last.fm key present.
  Audio proxy  ██░░░░░░░░  Heuristic estimates from genre/tag. Better than nothing, barely.

What it should look like:

  Anchors      ██████████  Human curation — the core, always
  Last.fm sim  ████████░░  Graph propagation + track.getSimilar (not just artist)
  Semantic ML  ████████░░  sentence-transformers local embeddings — real meaning matching
  Editorial    ████████░░  Spotify editorial playlists — highest-quality mood ground truth
  Lyrics NLP   ██████░░░░  Same, improved
  Deezer full  ██████░░░░  Full track fields, energy estimates
  AcoustBrainz ██████████  Real audio features for millions of tracks (offline dump)
  MusicBrainz  ██████░░░░  Same
```

---

## Phase 0 — Signal Integrity (do before next public push)

These are fixes that cost nothing and should happen immediately. No new dependencies.

### 0.1 — Zero out audio weight honestly when proxy
**Problem:** `audio_score` returns 0.0 for neutral vectors correctly, but `w_audio=0.14` still flows through the weight normalization and inflates other signals artificially. More importantly, the cohesion filter uses audio vectors for similarity — and all `[0.5]*6` vectors are perfectly similar to each other, so cohesion scores are fake.

**Fix:** When `audio_vector_source == "metadata_proxy"` or `"neutral"`, set `w_audio = 0.0` and renormalize remaining weights. Make cohesion filter use tag-Jaccard only (which is what `cohesion_filter()` in `scorer.py` does — verify it's being called everywhere instead of `cohesion.py`'s vector-based version).

**Impact:** Cohesion labels become honest. "Perfect fit" stops being a lie.

### 0.2 — Use Deezer full track fields
**Problem:** We hit Deezer's `/track/{id}` but only extract `bpm`. The endpoint also returns `gain` (loudness proxy for energy), `rank` (popularity), `explicit_content_lyrics`, `duration`, and for some tracks `preview` (30s clip URL).

**Fix:** Extract `gain` and normalize it to [0, 1] as an energy proxy. It's not Spotify audio features but it's better than `0.5`. A track with gain -3 dB is probably louder/more energetic than one at -9 dB. Store as `dz_energy` tag.

**Impact:** ~15-20% of tracks get a rough energy estimate that's real data, not a guess.

### 0.3 — Mine Spotify editorial playlists (hardcoded IDs)
**Problem:** Dev Mode blocks reading user playlist items (`playlist_items_blocked=True`). But Spotify's editorial/official playlists have stable public IDs and should be readable regardless of quota mode.

**Fix:** Hardcode 150-200 Spotify editorial playlist IDs across all mood categories (Mood Booster `37i9dQZF1DX3rxVfibe1L0`, Sad Songs `37i9dQZF1DXbrUpGvoi3TS`, Dark & Stormy `37i9dQZF1DX2yvmlOdMYzV`, etc.) into `playlist_mining.py`. Try reading their tracks; if blocked, fail silently. If readable, these are the highest-quality mood labels that exist — Spotify's own curators labeled every track.

**Test needed:** Verify in Dev Mode whether editorial playlist item reads succeed. If yes: this is a game-changer.

**Impact:** Potentially restores the full mining signal for the majority of moods using ground-truth editorial data.

### 0.4 — Cache system: audit, protect, and communicate

The caching system is already well-designed in code. The problem is that users (and the UX) treat it like a black box. One wrong button click wipes everything and the next scan silently becomes a 10-minute wait with no warning.

#### Full cache inventory

| File | What it stores | TTL | Incremental? | Safe to clear? |
|---|---|---|---|---|
| `.mining_cache.json` | Last.fm tag charts + playlist mining results for all 87 moods | **30 days** (auto-expires) | No — full re-mine on miss | Yes, costs ~55s |
| `.lastfm_cache.json` | Artist tag dictionaries + track tag dictionaries + similarity graph | **None** (permanent) | Yes — only uncached tracks fetched | Careful — full re-fetch costs 3-10 min for large libraries |
| `.deezer_cache.json` | Artist genres + per-track BPM/gain/rank | **None** (permanent) | Yes — only uncached tracks fetched | Yes for tracks sub-key; artist key is fast |
| `.audiodb_cache.json` | Artist/track mood + energy data from TheAudioDB | **None** (permanent) | Yes | Yes, costs ~90s first time |
| `.mb_cache.json` | MusicBrainz genre/tag lookups by MBID | **None** (permanent) | Yes | Yes, costs ~5 min |
| `.lyrics_cache.json` | lrclib lyrics + NLP sentiment results per track | **None** (permanent) | Yes — only uncached tracks fetched | Careful — re-fetching all lyrics costs 2-5 min |
| `.discogs_cache.json` | Discogs artist genre lookups | **None** (permanent) | Yes | Yes, costs ~5 min |
| `.acoustid_cache.json` | Local file fingerprint results | **None** (permanent) | Yes | Only needed for local library users |
| `.spotify_genres_cache.json` | Spotify API artist genre strings | **None** (permanent) | Yes | Yes, fast (Spotify API, no rate limit concern) |
| `.last_scan_snapshot.json` | Full scan result payload (all tracks, mood results, genre map) | **None** (written each scan) | N/A | Don't clear — this is what the app loads on browser refresh |
| `.vibesort_cache` | Spotipy OAuth token (not a data cache) | Managed by spotipy | N/A | Never clear manually — breaks auth |

#### What's working correctly right now

- Mining cache has a proper 30-day TTL with timestamp comparison — Full Scan automatically re-mines when stale, never re-mines when fresh. This is correct behavior.
- Last.fm, Deezer, lyrics, AudioDB are all incremental — a rescan only fetches data for tracks not already cached. A library of 2,620 tracks with a full Last.fm cache takes ~15 seconds to "re-fetch" (it just reads from disk). This is correct.
- Scan page shows mining cache age in the checkbox help text.
- The snapshot lets the app survive browser refreshes without re-scanning.
- Custom Scan checkboxes let you selectively clear individual caches.

#### What's broken or risky

**Problem 1: "Clear All Caches" in Settings has no time warning.**  
The Settings page has a "Clear All" button that wipes every cache file simultaneously. After clicking it, the next Full Scan will take 10-15 minutes on a 2,500+ track library. There's no warning about this. Users click it thinking "clean slate = faster" when the opposite is true.

**Fix:** Add a time estimate to the "Clear All" button: *"This will require a full re-fetch on your next scan (~10-15 min for a library of your size). Are you sure?"* Show it in a `st.warning()` before the confirm checkbox.

**Problem 2: Clearing the snapshot breaks browser-refresh continuity.**  
The Settings "Clear All" deletes `.last_scan_snapshot.json` along with enrichment caches. That file is not an API cache — it's the app's in-memory state, written after every scan. Clearing it means the next browser refresh loses all results until a re-scan. It should never be cleared via "Clear All" — only overwritten by running a new scan.

**Fix:** Remove `.last_scan_snapshot.json` from the "Clear All" targets. It's not an API cache.

**Problem 3: Full Scan and Custom Scan look the same weight to users.**  
A user who just wants to "refresh" might run a Custom Scan with every checkbox ticked, not realizing they've just reset 10 minutes of cached work. The options panel doesn't communicate cumulative time cost.

**Fix:** Add a live time estimate that updates as checkboxes are ticked:
```
☑ Re-mine mood playlists   → +55s
☑ Re-fetch Last.fm tags    → +8 min (2,450 uncached tracks)
☐ Re-fetch lyrics          → +3 min if ticked

Estimated scan time: ~9 min
```
The uncached track count comes from checking the cache files before the scan starts — we already have `_cache_age_str()` and the cache loading logic to do this.

**Problem 4: No visible cache age on the main scan page.**  
Users don't know whether their data is fresh or stale. A Last.fm cache from 6 months ago will be used without comment. If a user adds new music to Spotify, their scan re-scores fine — but the new tracks don't get Last.fm enrichment until the Last.fm cache is cleared.

**Fix:** Add a compact "Data freshness" panel below the scan buttons:
```
Data freshness:
  Last.fm tags      ██████████  3 days old     ✓ fresh
  Deezer BPM        ██████████  3 days old     ✓ fresh
  Playlist mining   ████░░░░░░  18 days old    ✓ fresh (expires in 12 days)
  Lyrics            ██████████  3 days old     ✓ fresh
  Last scan         ██████████  2 hours ago    2,620 tracks · 87 moods
```

#### Mapping cache clearing to scan presets (Phase 3.4)

When we implement the three scan depth presets, they should map to cache clearing as follows:

| Preset | Mining | Last.fm | Deezer | Lyrics | AudioDB | MB/Discogs | Snapshot |
|---|---|---|---|---|---|---|---|
| **Quick Rescore** | Never | Never | Never | Never | Never | Never | Overwritten |
| **Fresh Scan** | If >7d old | New tracks only | New tracks only | New tracks only | Never | Never | Overwritten |
| **Deep Scan** | Always | Full clear | Full clear | Full clear | Full clear | Full clear | Overwritten |

"Quick Rescore" is: re-run scoring against all currently-cached enrichment data, no API calls. Under 1 minute always.  
"Fresh Scan" is: fetch enrichment for any tracks added since last scan, keep everything else. 1-3 minutes.  
"Deep Scan" is: wipe all enrichment caches, re-fetch everything from scratch. 10-15 minutes. User is warned before starting.

The snapshot is always overwritten by any scan — never cleared as part of cache management.

**Impact:** Users stop accidentally triggering 10-minute waits. Power users can still force full re-fetches. The cache system works the same as it does today — we just make it legible.

---

## Phase 1 — Human Curation Depth (the core work)

This is the most important phase. The algorithm is the vehicle; the curation is the destination.

### 1.1 — Anchor expansion: 6 → 12-15 per mood, era-diverse
**Current:** 546 anchors, avg 6.3 per mood. Functional minimum.  
**Target:** 900-1000 anchors, avg 11-12 per mood.

**Principles for good anchors:**
- Era coverage: every mood should have anchors from at least 3 decades
- Sub-genre coverage: a "dark" mood shouldn't only have indie — it should have dark hip-hop, dark electronic, dark folk
- Obscurity balance: 70% well-known (high Spotify search hit rate), 30% deep cuts (the taste signal)
- Disagreement test: if you'd argue about whether a track belongs, it's a bad anchor

**Moods that need the most anchor work right now:**
- `Hollow` — currently indie-heavy, needs dark R&B, dark hip-hop, post-punk representation
- `Villain Arc` — needs more variety beyond hype rap
- `Liminal` — currently conceptually strong but poorly anchored
- `Same Vibe Different Genre` — almost meaningless without great anchors; this mood is entirely anchor-driven
- `Psychedelic` — needs 60s/70s classics, modern psych, psych-adjacent electronic
- `Sundown` — needs 70s/80s mellow rock, not just 90s/2000s
- `Deep Focus` — instrumental coverage is thin

### 1.2 — Negative anchors ("this track must never appear here")
**Problem:** We have `forbidden_tags` and `forbidden_genres` but they're probabilistic. Some specific tracks will always wrongly score high for a mood because their genre matches but their feel is completely off.

**Implementation:** Add a `"negative_anchors"` list to each mood in `packs.json`. Tracks in this list get a hard score cap of 0.05 — they can appear in the pool but never rank into the final playlist.

**Example:** "Enter Sandman" (Metallica) is not a `Metal Testimony` (Christian metal) track. "Happy" (Pharrell) is not "Hollow". These should be explicitly excluded.

### 1.3 — Mood list expansion: 87 → 110-120
**Philosophy:** Only add a mood if you can name 10 tracks that unambiguously belong to it and 10 that don't. No mood that could be a genre playlist (those are covered by the genre system). No mood that's a subset of an existing mood without a clear differentiating character.

**Gaps in the current 87:**

*Currently missing or too thin:*

| Proposed Mood | Character | Example Anchors |
|---|---|---|
| **2000s Pop Maximalism** | Overproduced, bombastic pop — Britney, NSYNC, Spice Girls, early Beyoncé | "Baby One More Time", "Toxic", "Hips Don't Lie" |
| **Y2K Nostalgia** | That specific late-90s/early-2000s electronic-meets-pop texture | Daft Punk, Basement Jaxx, Chemical Brothers crossover |
| **Cinematic Swell** | Orchestral builds, film score energy, Hans Zimmer territory | "Time", "Experience" (Einaudi), "Pirates of the Caribbean" |
| **Protest Song** | Anger with purpose, political clarity — not rage, not party | "Fight the Power", "The Revolution Will Not Be Televised", "Alright" |
| **Breakup Bravado** | Post-breakup confidence, not sadness — reclaiming yourself | "thank u, next", "Since U Been Gone", "Cry Me a River" |
| **Cabin in the Woods** | Hyper-specific: acoustic, isolated, winter, wood smoke | Bon Iver's first album energy, Iron & Wine, early Fleet Foxes |
| **New Love High** | That specific early-relationship euphoria, not generic happy | "Electric Love", "Can't Help Falling in Love", "XO" |
| **Sunday Morning Soft** | Slower than Morning Ritual, more domestic — coffee, no plans | Norah Jones, Jack Johnson, Ben Harper slow songs |
| **Gym Floor Banger** | Actual workout energy, not just hype — rhythm-driven, physical | "Till I Collapse", "Power", "Run the World" |
| **Jazz Late Bar** | Not Jazz Nights (which is general) — specifically late, sparse, smoky | Miles Davis Kind of Blue era, Bill Evans, Chet Baker |
| **Screaming Into the Void** | Cathartic loud release — not angry, not sad, just big | Sigur Rós loud passages, Godspeed You!, Mogwai |
| **Internet Brain** | ADHD-coded, hyperpop-adjacent but not hyperpop, ironic, fast | PC Music, 100 gecs adjacent, Dorian Electra |
| **Doomscroll 4AM** | Not quite 3AM Unsent Texts — more dissociated, screen-lit, numb | That slightly wrong vibe of being awake too late online |
| **Earned Wisdom** | Songs that feel like they're from someone who's been through it | Late-career Springsteen, Leonard Cohen, Joni Mitchell older work |
| **Workout Cool-Down** | Post-exercise — the body is tired, the mind is clear | Different from Deep Focus; physically spent but content |
| **Midsummer Night** | That specific warmth of a night that doesn't cool down | Tropical but not party — Vampire Weekend, Unknown Mortal Orchestra |
| **Acoustic Covers** | When the stripped version is better than the original | Jeff Buckley Hallelujah, Johnny Cash Hurt, Lana Del Rey Once Upon a Dream |
| **Film Noir Walk** | Cinematic dark cool — not rage, not sad — stylized darkness | Portishead, Massive Attack, Nick Cave |
| **Post-Game Locker Room** | Victory lap, tired satisfaction, team energy | "We Are the Champions", "Eye of the Tiger", but also "Started From the Bottom" |
| **Getting Your Life Together** | Hopeful productivity — not motivation-poster, actually personal | Specific mix of determination and quiet resolve |
| **Parasocial Crush** | That specific feeling of parasocial attachment to a creator/character | Parasocial anthems, stan culture songs |
| **Reading in the Rain** | A narrower Lo-Fi — specifically for concentration with weather | More specific/intentional than Chillhop Cafe |
| **Revenge Served Cold** | Not Villain Arc (power) — this is calculated, patient, quiet | "Resentment", "You Oughta Know", "Pray for Me" |

**Anti-patterns (don't add these):**
- Moods that are just genre labels ("Midwest Emo", "UK Garage") — those belong in the genre system
- Moods that duplicate existing ones closely ("Sleepy Sad" ≈ Rainy Window)
- Moods no one will have enough tracks for (<10 tracks in most libraries)

### 1.4 — Mood metadata deepening
Every mood should have, beyond what we have now:
- `vibe_sentence` — one line a human would actually say ("for when you need to feel like you're the main character of a heist film")
- `time_of_day_weight` — which TOD tags make a track more/less appropriate for this mood
- `listener_archetype` — who this mood is for ("the person who cried at the end of Good Will Hunting")
- `anti_mood` — the opposite mood (Hollow ↔ Golden Hour; Villain Arc ↔ Sunday Reset)

These don't affect scoring — they affect the UI and make the product feel like it was made by someone with taste, not an algorithm.

---

## Phase 2 — Intelligence Upgrade

### 2.1 — Last.fm `track.getSimilar` in graph propagation
**Current:** Graph propagation uses `artist.getSimilar` — if Radiohead is similar to Portishead, all Radiohead tracks get Portishead's mood tags.  
**Problem:** Track-level signals are flattened to artist level. "Creep" and "OK Computer" are very different moods but share the same artist-level propagation.

**Fix:** After anchor matching, call `track.getSimilar` for each anchor track (not just the artist). Walk the similarity graph at track level. This is the same free Last.fm API, same key — just a different endpoint. Expected: 3-5x more precise mood tagging.

**Rate limit consideration:** 1 req/sec, cache aggressively. For a 2,620-track library, worst case is ~45 minutes on first run. Cache indefinitely since track similarity is stable.

### 2.2 — sentence-transformers local semantic layer
**Current:** `semantic_score()` does token overlap — "night" matches "night_drive". Not semantics.  
**Target:** A local model that understands "3am emptiness" and "hollow introspective dark" are the same thing.

**Implementation:**
- Model: `all-MiniLM-L6-v2` (80 MB, Apache 2.0, CPU-friendly)
- At scan time: embed each track's assembled description (genre + top tags + artist name + track name)
- Embed each mood's `vibe_sentence` + `semantic_core` joined
- Cosine similarity → replaces current token-overlap `semantic_score()`
- Precompute all track embeddings once, cache to disk
- Only recompute for new tracks

**Dependency:** `sentence-transformers` (~200 MB with model). Optional — degrade gracefully if not installed. Add to `requirements.txt` behind a `[ml]` extra.

**Impact:** The 7 moods that returned zero results partly because their semantic_core couldn't token-match → now match by meaning. "Weightless" gets tracks that feel weightless, not tracks that have the word "weightless" in their tags.

### 2.3 — AcoustBrainz offline data
**What it is:** AcoustBrainz was a community-sourced acoustic analysis project (now offline) that computed high-level mood, energy, danceability, tonal features for ~8 million tracks. The full data dump is freely downloadable (~50 GB compressed).

**What we get:** Real audio features — not Spotify's proprietary ones, but independently computed — covering most of the classic/popular catalog. This restores the audio signal for tracks that have MBIDs.

**Implementation:**
- Download the `acousticbrainz-highlevel-json-20220623.tar.bz2` dump (one-time, maintainer-side)
- Build a lookup SQLite database: MBID → {mood_acoustic, danceability, gender, tonal, key}
- At enrichment time: if a track has an MBID (MusicBrainz lookup already does this), query the local SQLite
- Replace the `metadata_proxy` vector with the AcoustBrainz vector

**User-facing:** Optional. Works silently if the database file exists in `data/`. Document how to download.

### 2.4 — Emergent clustering layer
**Current:** Every track is scored against 87 predefined moods. The moods are our assumptions.  
**Alternative:** Build a track-track similarity graph from all available signals, run Louvain community detection, identify natural clusters, then label them against our mood definitions.

**Why this matters:** If a user has 400 shoegaze tracks, they have mood sub-clusters within shoegaze that we currently collapse into one. The clustering layer surfaces what's actually in the library, then maps to moods rather than forcing tracks into boxes.

**Implementation:**
- Build weighted similarity graph: edges between tracks sharing tags, anchors, Last.fm similarity
- Louvain clustering (`python-louvain`, MIT license, pure Python)
- For each cluster: score it against all 87 moods → assign the best-matching mood label
- Report unmatched clusters to user as "discovered" moods without labels
- This runs post-scoring as an enhancement layer, not a replacement

---

## Phase 3 — Connection & Onboarding

The core problem: every useful data source requires manual `.env` editing. That's a dev workflow, not a user workflow.

### 3.1 — Last.fm OAuth in-app
**Current:** User must get a Last.fm API key, manually edit `.env`, restart app.  
**Target:** Click "Connect Last.fm" in the UI → enter username + password → done. Or even simpler: username only (public data doesn't require auth).

**Implementation:** Last.fm has a web auth flow (similar to Spotify). The app opens the Last.fm auth URL, user approves, callback returns a session key. Store in `.env` or Streamlit session. For read-only scrobble data: just a username is enough — no auth needed.

**Quick win version:** Just a username field on the Connect page that stores to `.env` and uses the bundled app-level API key (which we already have). No OAuth needed for reading public scrobble history. Ship this first.

### 3.2 — Streaming history drag-and-drop
**Current:** User must download their Spotify extended history, read the docs, find the `data/` folder, drop files there.  
**Target:** A file upload zone on the Connect page: "Drop your Spotify history files here". Streamlit's `st.file_uploader` handles this natively. Save to `data/` automatically.

**Also support:** Apple Music data export (`.csv` from Apple), YouTube Music Takeout (`.json` from Google Takeout).

### 3.3 — First-run wizard
**Current:** App opens → Connect page → immediately asked to connect Spotify → nothing explains what's happening.  
**Target:** First launch (detected by absence of any cache) shows a 3-step wizard:

```
Step 1: Connect Spotify (required — 30 seconds)
Step 2: Connect Last.fm (optional — enter username, big signal boost)
Step 3: Choose scan depth (Quick — 3 min / Full — 8 min / Deep — 20 min)
```

One screen, no sidebar navigation until wizard complete. Progress shown clearly.

### 3.4 — Scan depth presets
**Current:** Custom scan with checkboxes — confusing to non-technical users.  
**Target:** Three named presets on the scan page:

| Preset | What it does | Time |
|---|---|---|
| **Quick Rescore** | Re-runs scoring only from cached data | <1 min |
| **Fresh Scan** | Re-fetches Last.fm + Deezer, re-scores | 3-5 min |
| **Deep Scan** | Clears all caches, re-fetches everything, re-mines | 8-15 min |

Custom scan stays available as an "Advanced" collapse.

### 3.5 — Progress that actually tells you what's happening
**Current:** Progress bar + a log line. "Running playlist mining..." for 3 minutes.  
**Target:** Human-readable substeps:

```
✓ Connected to Spotify — 2,620 songs found
✓ Loaded genre tags — 1,847 tracks enriched
⟳ Fetching Last.fm mood data — 847/2620 tracks (2m remaining)
  Pulling similar tracks for your anchors...
⟳ Running mood scoring — 45/87 moods done
```

---

## Phase 4 — Public GitHub Release

### 4.1 — GitHub Releases with portable zip as asset
**Current:** Zip must be built manually, stored locally, shared by link.  
**Target:** Every git tag triggers a GitHub Actions workflow that:
- Builds the Windows portable zip (downloads Python embed + installs deps)
- Uploads it as a GitHub Release asset
- Creates release notes from commits since last tag

Non-technical users get: `https://github.com/PapaKoftes/VibeSort/releases/latest` → download → unzip → run. No command line ever.

### 4.2 — Windows SmartScreen / "unknown publisher" problem
**Current:** Unzipping and running `run.bat` triggers "Windows protected your PC" for most users.  
**Options:**
- **A (free):** Ship a `START HERE.bat` instead of `run.bat` with a clear name. Add `README_FIRST.txt` explaining the SmartScreen click-through. Most users can handle "More info → Run anyway" once you explain it.
- **B (free, better):** Codesign the `.bat` or `.vbs` with a free Certum/SignPath open-source code signing certificate. Eliminates SmartScreen entirely.
- **C (paid):** Extended Validation cert (~$200/yr). Full trust immediately.

**Recommendation:** Option A for now with very clear instructions. Option B when we have bandwidth.

### 4.3 — Spotify Dev Mode friend onboarding
**Current:** Manual process — get friend's Spotify email, add to dashboard, they wait.  
**Until we get extended quota:** Document this clearly as a beta feature. Make the Connect page show a waiting-list-style message if the user is blocked, with a link to request access.

**Target (extended quota):** Apply for Spotify Extended Quota Mode once the app is more polished. Requirements: privacy policy, terms of service, screenshot of working app, description of use case. We meet all of these now.

### 4.4 — Privacy policy and terms of service
**Required for:** Spotify extended quota application, Apple Music API, any user-facing hosting.  
**Content:** Simple. The app runs locally. No data leaves the machine except:
- API calls to Spotify (required)
- API calls to Last.fm, Deezer, MusicBrainz, Genius (enrichment, optional)
- No analytics, no server, no account creation

Create `docs/PRIVACY.md` and `docs/TERMS.md`. Link from README and Connect page.

### 4.5 — `CONTRIBUTING.md` and mood submission process
**The most valuable contribution a non-developer can make:** Adding anchor tracks to moods.  
**Process:**
- `data/mood_anchors.json` is the main curation file
- A non-developer can open it, find their mood, add `{"artist": "X", "title": "Y"}` to the list
- PR → review → merge → next release includes their curation

Document this clearly. It's the community flywheel.

---

## Mood List — Target State

### Keep all 87 current moods. Add 20-25 more.

**Priority additions (highest confidence these belong):**

| Mood | Priority | Reason |
|---|---|---|
| Cinematic Swell | High | Gap — no orchestral/score mood |
| Protest Song | High | Gap — politically purposeful anger is distinct from Villain Arc/Rage Lift |
| Breakup Bravado | High | Gap — post-breakup confidence distinct from Heartbreak |
| New Love High | High | Gap — early relationship euphoria distinct from Golden Hour (general happy) |
| Y2K Nostalgia | High | Large catalog, very specific texture, highly recognizable |
| Film Noir Walk | High | Portishead/Massive Attack/trip-hop has no home currently |
| Gym Floor Banger | Medium | Workout energy is distinct from Rage Lift (rage) and Adrenaline (general) |
| Cabin in the Woods | Medium | Narrower than Acoustic Corner — more isolated/winter/raw |
| Jazz Late Bar | Medium | Jazz Nights covers daytime jazz; this covers 2am sparse jazz |
| Screaming Into the Void | Medium | Post-rock catharsis — Sigur Rós loud passages, Mogwai, Godspeed |
| 2000s Pop Maximalism | Medium | Large catalog, specific nostalgia |
| Earned Wisdom | Medium | Late-career artists, songs from experience — no home currently |
| Internet Brain | Low | ADHD/ironic/fast — niche but real |
| Revenge Served Cold | Low | Calculated vs. Villain Arc's hot energy |
| Midsummer Night | Low | Tropical warmth without party — Unknown Mortal Orchestra territory |

**Total target: 102-112 moods**

---

## Release Criteria Checklist

A mood is ship-ready when:
- [ ] 10+ anchor tracks, era-diverse (at least 3 decades represented)
- [ ] `expected_tags` use only real, mineable tag strings
- [ ] `preferred_macro_genres` is populated (no empty arrays)
- [ ] `vibe_sentence` written (human-readable one-liner)
- [ ] At least one negative anchor identified
- [ ] Tested: produces 20+ tracks in a 2,000+ song library scan

The app is ship-ready when:
- [ ] All 87 (+ new) moods pass the above
- [ ] Track coverage ≥ 50% in a typical library (currently ~35% projected post-fix)
- [ ] Cohesion labels are honest (audio proxy weight zeroed when neutral)
- [ ] Last.fm username field is in-app (no `.env` editing for most important signal)
- [ ] Streaming history upload is drag-drop
- [ ] Portable zip auto-builds in CI on tag
- [ ] Privacy policy exists
- [ ] README has a real screenshot of actual results (not mockups)
- [ ] Spotify extended quota applied for (or SmartScreen workaround documented)
- [ ] Windows SmartScreen instructions clear
- [ ] First-run experience is coherent for a non-technical user

---

## Priority Order (next 2 weeks)

1. **Scan results review** — after current scan completes, evaluate actual mood quality, track coverage, what the 7 fixed moods produce. This is ground truth.
2. **Phase 0.1** — Zero out audio weight honestly. One function change. Do it.
3. **Phase 0.3** — Test editorial playlist reading in Dev Mode. If it works: implement immediately. Highest leverage.
4. **Phase 1.1** — Anchor expansion to 12-15 per mood. Pure curation work. No code.
5. **Phase 1.2** — Negative anchors. Small code addition, high quality impact.
6. **Phase 1.3** — Add the top 8 new moods. Pure curation + `packs.json` additions.
7. **Phase 3.1** — Last.fm username field in-app. Small UI change, massive signal impact for users.
8. **Phase 3.2** — Drag-drop streaming history.
9. **Phase 4.1** — GitHub Actions release automation.
10. **Phase 2.1** — `track.getSimilar` (requires Last.fm key, higher complexity).
11. **Phase 2.2** — sentence-transformers (higher complexity, biggest semantic impact).
12. **Phase 3.3** — First-run wizard.
13. **Phase 2.4** — Clustering layer.
14. **Phase 2.3** — AcoustBrainz (requires one-time setup, big payoff).

---

## The honest north star

The app does something genuinely valuable: it organizes music by feel, not by genre or BPM. Spotify doesn't do this. Apple Music doesn't. The algorithmic playlists are bland. A human could spend 200 hours making these playlists manually for their library — we do it in 10 minutes.

The gap we need to close: **the results have to feel like they were curated by someone with taste, not generated by a classifier.** Right now they're 70% of the way there. The remaining 30% is:
- More anchors per mood (more human signal)
- Real semantic matching (the algorithm understanding what a mood *means*)
- Editorial playlist data (ground truth from Spotify's own curators)
- Honest signal display (stop claiming "Perfect fit" when the audio vector is fake)

When those four things are done, the product is ready to be proud of publicly.
