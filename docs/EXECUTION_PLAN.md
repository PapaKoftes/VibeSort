# Vibesort — Execution Plan: Every Component to 10/10

> Ordered by impact-per-hour. Each item has a confidence score target,
> exact file/line, and implementation spec. Nothing vague.

---

## Sprint 1 — Zero-cost fixes (no new dependencies, ~3 hours total)

These are all bugs or omissions in existing code. No new libraries. Run a scan after this block and check coverage.

---

### 1.1 — Use `dz_gain` as energy proxy in audio_proxy.py
**Confidence lift:** audio_score 2/10 → 4/10  
**Time:** 30 min  

`gain` is already fetched from Deezer's `/track/{id}` and stored in `track_tags` as `dz_gain`. It is never read in `audio_proxy.py`. Fix:

In `core/audio_proxy.py`, find where `dz_bpm` is read. Add:
```python
# dz_gain: Deezer replay-gain (negative dBFS). Higher = louder/more energetic.
# Range typically -14dB (quiet) to -3dB (loud). Normalize to [0,1].
dz_gain_raw = tags.get("dz_gain")
if dz_gain_raw is not None:
    # Clamp to typical range, invert sign, normalize
    dz_energy = max(0.0, min(1.0, (float(dz_gain_raw) + 14.0) / 11.0))
    vector[1] = dz_energy  # energy slot
```
This gives real energy estimates for all tracks with Deezer coverage (~70%).

---

### 1.2 — Zero audio weight explicitly when all vectors are neutral proxy
**Confidence lift:** audio_score integrity 2/10 → 5/10  
**Time:** 20 min  

In `core/scorer.py`, `effective_score_weights()` already redistributes weight for proxy mode. But when `dz_gain` is absent and source is `metadata_proxy`, the energy estimate is pure genre heuristic (unreliable). Add a guard:

In `effective_score_weights()`, after detecting proxy mode, check if the audio vector is fully heuristic (all values ≈ 0.5 ± 0.05). If so, return `w_audio = 0.0` and redistribute to tags:
```python
_is_fully_neutral = all(abs(v - 0.5) < 0.06 for v in (profile.get("audio_vector") or []))
if _is_proxy and _is_fully_neutral:
    # Pure heuristic — no real audio data. Zero weight, give to tags.
    excess = w_audio
    w_audio = 0.0
    w_tags = min(1.0, w_tags + excess * 0.7)
    w_semantic = min(1.0, w_semantic + excess * 0.3)
```

---

### 1.3 — Fire `track.getSimilar` for ALL library tracks, not just low-confidence
**Confidence lift:** anchor graph hit 8.2% → 25-35%  
**Time:** 45 min  

`get_similar_track_tags()` in `core/lastfm.py` is already implemented. But in `scan_pipeline.py`, it's only called for `_sim_candidates` (tracks that are already low-confidence). Fix: call it for all tracks that have at least one Last.fm tag but zero anchor/graph tags. This is the biggest signal improvement available with zero new code.

In `scan_pipeline.py`, around line 1040 where `_sim_candidates` is built:
```python
# Current: only "untagged" tracks get getSimilar
# Fix: also run for tracks with tags but no anchor/graph signal
_sim_candidates = [
    t for t in all_tracks
    if track_tags.get(t.get("uri",""))  # has some tags
    and not any(
        k.startswith(("anchor_", "graph_mood_", "personal_anchor_"))
        for k in track_tags.get(t.get("uri",""), {})
    )
]
```
This expands the candidate pool from ~200 to ~2000+ tracks, dramatically improving graph reach.

**Rate limit note:** Already handled with 1 req/sec throttle + cache. For a 2,621-track library with ~2,000 candidates, first run ≈ 35 min (runs in the background of the scan). Cached permanently after — subsequent scans ≈ 0 additional time.

---

### 1.4 — Test and implement Spotify editorial playlist mining
**Confidence lift:** playlist mining 1/10 → 6/10 (if readable) or stay at 1/10 (if blocked)  
**Time:** 1 hour  

Test whether Dev Mode blocks Spotify's own editorial playlists. These are the highest-quality mood labels that exist.

Add to `core/playlist_mining.py` a hardcoded editorial ID list and test function:
```python
EDITORIAL_PLAYLISTS = {
    # Mood Booster
    "37i9dQZF1DX3rxVfibe1L0": ["happy", "upbeat", "energetic", "feel_good"],
    # Sad Songs
    "37i9dQZF1DXbrUpGvoi3TS": ["sad", "melancholic", "lyr_sad", "heartbreak"],
    # Dark & Stormy
    "37i9dQZF1DX2yvmlOdMYzV": ["dark", "stormy", "moody", "atmospheric"],
    # Peaceful Piano
    "37i9dQZF1DX4sWSpwq3LiO": ["calm", "peaceful", "focus", "instrumental"],
    # Rap Caviar
    "37i9dQZF1DX0XUsuxWHRQd": ["rap", "hype", "trap", "lyr_money"],
    # Gold School
    "37i9dQZF1DXbYM3nMM0oPk": ["90s", "classic", "nostalgia"],
    # Viva Latino
    "37i9dQZF1DX10zKzsJ2jva": ["latin", "reggaeton", "tropical"],
    # Are & Be (R&B)
    "37i9dQZF1DX4SBhb3fqCJd": ["rnb", "soul", "smooth", "lyr_love"],
    # +100 more across all mood categories
}
```

In `mine()`, after the standard mining pass, attempt editorial reads. If they succeed (not blocked), they become the highest-weight source. If blocked, log once and skip silently.

---

### 1.5 — Remove snapshot from "Clear All Caches" in Settings
**Confidence lift:** cache UX 0/10 → 6/10  
**Time:** 10 min  

In `pages/9_Settings.py`, find `cache_files` dict and remove the snapshot entry. Add a time estimate warning before the Clear All button.

---

### 1.6 — Filter `dz_bpm` from top_tags display (it's noise, not a mood signal)
**Confidence lift:** data integrity display quality  
**Time:** 10 min  

`dz_bpm` appears as the #1 "top tag" in many moods because it's a numeric pseudo-tag stored alongside real tags. Filter it from display anywhere `top_tags` is shown.

In `core/scan_pipeline.py`, where `top_tags` is computed for the payload:
```python
_DISPLAY_FILTER = {"dz_bpm", "dz_gain", "meta_opener", "meta_single", "meta_feature", "meta_explicit"}
top_tags = [t for t in top_tags_raw if t not in _DISPLAY_FILTER]
```

---

## Sprint 2 — Human curation (the most impactful work, no code required)

This is the soul of the product. No code changes needed — just `data/mood_anchors.json` and `data/packs.json`.

---

### 2.1 — Anchor expansion: 6.4 avg → 12-15 per mood
**Confidence lift:** anchor graph hit 8.2% → 40-50% post-getSimilar fix  
**Time:** 4-6 hours of focused curation  

**Target:** 558 → 1,050+ anchors. Each anchor must be unambiguous — if you'd argue about it, it's a bad anchor.

**Rules per mood:**
- Era diversity: at least 3 decades represented
- Sub-genre diversity: don't over-index one sub-style
- 70% well-known (high Spotify search hit rate), 30% deep cuts

**Priority moods** (thinnest, most impactful to expand first):

| Mood | Current | Add These (examples) |
|---|---|---|
| Hollow | 6 | The National "Bloodbuzz Ohio", Sufjan Stevens "Should Have Known Better", Cigarettes After Sex "Apocalypse", Daughter "Youth", Beach House "Space Song", Elliott Smith "Between the Bars" |
| Rainy Window | 6 | Mazzy Star "Fade Into You", Portishead "Glory Box", Nick Cave "Into My Arms", Grouper "Vapor Trail", Adrianne Lenker "anything" |
| Late Night Drive | 6 | Kavinsky "Nightcall", Chromatics "Night Drive", M83 "Midnight City", Com Truise "Galactic Melt", Gunship "Tech Noir" |
| Liminal | 6 | William Basinski "Disintegration Loop 1.1", Stars of the Lid "Requiem for Dying Mothers", Tim Hecker "Hatred of Music I", Actress "R.I.P.", The Caretaker "An Empty Bliss Beyond This World" |
| Villain Arc | 6 | Pusha T "Infrared", Rick Ross "B.M.F.", Migos "Bad and Boujee", Future "Mask Off", Playboi Carti "Magnolia" |
| Rage Lift | 6 | System of a Down "BYOB", Disturbed "Down with the Sickness", Tool "Schism", Pantera "Walk", Deftones "My Own Summer" |
| Afterparty | 6 | Justice "D.A.N.C.E.", Daft Punk "Get Lucky", Disclosure "Latch", Duke Dumont "I Got U", MK "17" |

For every mood, follow the same expansion template — the `data/mood_anchors.json` format is trivial:
```json
{"artist": "Artist Name", "title": "Track Title"}
```

---

### 2.2 — Negative anchors: add to every mood
**Confidence lift:** playlist quality 6/10 → 8/10  
**Time:** 2-3 hours  

Add `"negative_anchors"` key to every mood in `packs.json`. These tracks hard-cap at score 0.05 — they can never rank into the final playlist regardless of their tag/genre scores.

**Implementation needed in `core/scorer.py`:** Add to `score_track()`:
```python
neg_anchors = mood_negative_anchors(mood_name)  # reads from packs.json
if profile.get("uri") in neg_anchors:
    return min(base, 0.05)
```

**Anchor lookup precomputation** in `core/anchors.py`: build a URI→mood set at scan start.

**Examples per mood:**
- Hollow: "Happy" (Pharrell Williams), "Can't Stop the Feeling" (Justin Timberlake)
- Morning Ritual: "Fade to Black" (Metallica), "Hurt" (NIN)
- Villain Arc: "What a Wonderful World" (Armstrong), "Here Comes the Sun" (Beatles)

---

### 2.3 — Add `vibe_sentence` and `anti_mood` to all moods
**Confidence lift:** UI polish, product feel  
**Time:** 2 hours  

No scoring impact. Pure product feel. Add to each mood in `packs.json`:

```json
"vibe_sentence": "for when you need to feel like you're the main character of a heist film",
"anti_mood": "Sunday Reset",
"listener_archetype": "the person who rewatches the same 3 films every winter"
```

Show `vibe_sentence` on the mood card in `3_Vibes.py` instead of the generic description.

---

### 2.4 — Audit `expected_tags` against real Last.fm tag database
**Confidence lift:** tag_score 7/10 → 9/10  
**Time:** 1 hour  

Some expected_tags are invented strings that will never appear in real Last.fm data. Run this check:

```python
# For each expected_tag across all moods:
# 1. Hit Last.fm tag.getInfo API
# 2. Check if tagcount > 1000 (real tag) vs tagcount < 100 (invented)
# 3. Replace invented tags with real equivalents
```

Known invented tags to replace now:
- `lyr_violence` → `violent` (real Last.fm tag)
- `lyr_heartbreak` → `heartbreak` (real, don't double up)
- `lyr_hype` → `hype` (same tag)
- `chamber_pop` → `chamber pop` (space not underscore)
- `classic_country` → `classic country`
- `sea_shanty` → `sea shanty`

Fix: use `tag.replace("_", " ")` when looking up against Last.fm's tag vocabulary.

---

### 2.5 — Add 20-25 new moods
**Confidence lift:** coverage and depth  
**Time:** 4-6 hours  

Priority order from ROADMAP.md. Each new mood needs:
- [ ] `packs.json` entry with all fields (description, expected_tags ≥8, preferred_macro_genres, audio_target, forbidden_tags, forbidden_genres)
- [ ] `mood_anchors.json` entry with 8+ anchors
- [ ] `vibe_sentence`

**Build order** (highest library hit rate first):
1. **Film Noir Walk** (Portishead/Massive Attack/trip-hop has no home — large catalog)
2. **Breakup Bravado** (post-breakup confidence — distinct from Heartbreak, large pop catalog)
3. **New Love High** (early relationship euphoria — distinct from Golden Hour, huge pop catalog)
4. **Cinematic Swell** (orchestral builds — Hans Zimmer territory, no home currently)
5. **Y2K Nostalgia** (late 90s/early 2000s texture — massive recognizable catalog)
6. **Protest Song** (purposeful anger — distinct from Villain Arc/Rage Lift)
7. **Gym Floor Banger** (workout energy — distinct from Adrenaline)
8. **Cabin in the Woods** (isolated acoustic winter — narrower than Acoustic Corner)
9. **Jazz Late Bar** (2am sparse — distinct from Jazz Nights)
10. **Earned Wisdom** (late-career artists, songs from experience)

---

## Sprint 3 — ML signal upgrades (~1-2 days, new dependencies)

---

### 3.1 — sentence-transformers: real semantic matching
**Confidence lift:** semantic_score 4/10 → 8/10  
**Time:** 4-6 hours (including testing)  

**Model:** `all-MiniLM-L6-v2` (80MB, Apache 2.0, CPU-friendly, 384-dim embeddings)

**Add to `requirements.txt`:**
```
sentence-transformers>=2.7.0
```
Add to optional install section: `pip install vibesort[ml]`.

**New file: `core/semantic_embed.py`**
```python
"""
Real semantic matching via sentence-transformers.
Replaces token-overlap semantic_score() when model is available.
Falls back to existing token overlap if not installed.
"""
import os, pickle, numpy as np
from pathlib import Path

_MODEL = None
_CACHE_PATH = Path("outputs/.semantic_cache.pkl")
_MOOD_EMBED_PATH = Path("outputs/.mood_embeddings.pkl")

def _model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL

def embed_text(text: str) -> np.ndarray:
    return _model().encode(text, normalize_embeddings=True)

def embed_tracks(profiles: dict) -> dict[str, np.ndarray]:
    """Return {uri: embedding} for all tracks, loading from cache for known tracks."""
    cache = {}
    if _CACHE_PATH.exists():
        with open(_CACHE_PATH, "rb") as f:
            cache = pickle.load(f)
    
    new_uris = [uri for uri in profiles if uri not in cache]
    if new_uris:
        texts = []
        for uri in new_uris:
            p = profiles[uri]
            name = p.get("name", "")
            artists = ", ".join(p.get("artists", []) if isinstance(p.get("artists",[]), list) 
                              and p.get("artists") and isinstance(p["artists"][0], str) 
                              else [a.get("name","") for a in p.get("artists",[]) if isinstance(a,dict)])
            tags = " ".join(list(p.get("tags", {}).keys())[:15])
            genres = " ".join(p.get("macro_genres", []))
            texts.append(f"{artists} {name} {genres} {tags}")
        
        embeddings = _model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
        for uri, emb in zip(new_uris, embeddings):
            cache[uri] = emb
        
        _CACHE_PATH.parent.mkdir(exist_ok=True)
        with open(_CACHE_PATH, "wb") as f:
            pickle.dump(cache, f)
    
    return cache

def embed_moods(mood_defs: dict) -> dict[str, np.ndarray]:
    """Return {mood_name: embedding} for all mood semantic cores."""
    if _MOOD_EMBED_PATH.exists():
        with open(_MOOD_EMBED_PATH, "rb") as f:
            return pickle.load(f)
    
    result = {}
    for name, defn in mood_defs.items():
        core = defn.get("semantic_core", [])
        vibe = defn.get("vibe_sentence", "")
        text = " ".join(core) + " " + vibe
        result[name] = embed_text(text)
    
    with open(_MOOD_EMBED_PATH, "wb") as f:
        pickle.dump(result, f)
    return result

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # pre-normalized
```

**In `core/scorer.py`:** Replace `semantic_score()` token overlap with:
```python
def semantic_score(profile: dict, mood_name: str) -> float:
    # Try real embeddings first
    _emb = profile.get("_semantic_embedding")
    _mood_emb = _MOOD_EMBEDDINGS.get(mood_name)
    if _emb is not None and _mood_emb is not None:
        import numpy as np
        return float(max(0.0, min(1.0, np.dot(_emb, _mood_emb))))
    # Fallback: token overlap (existing implementation)
    return _semantic_score_token_overlap(profile, mood_name)
```

**In `core/scan_pipeline.py`:** After building profiles, inject embeddings:
```python
try:
    from core.semantic_embed import embed_tracks, embed_moods
    _track_embeddings = embed_tracks(profiles)
    _mood_embeddings = embed_moods(packs_data)
    for uri, emb in _track_embeddings.items():
        if uri in profiles:
            profiles[uri]["_semantic_embedding"] = emb
    scorer._MOOD_EMBEDDINGS = _mood_embeddings
    step("Semantic embeddings loaded", 35)
except ImportError:
    step("Semantic ML not available (pip install vibesort[ml])", 35)
```

---

### 3.2 — AcoustBrainz: real audio features for ~8M tracks
**Confidence lift:** audio_score 2/10 → 7/10  
**Time:** 2-3 days (data prep) + 4 hours (code)  

**One-time setup** (maintainer side):
1. Download `acousticbrainz-highlevel-json-20220623.tar.bz2` (~50GB compressed)
2. Run provided extraction script to build SQLite: MBID → {mood_acoustic, danceability, key, tonal_vector}
3. Ship SQLite as optional download (link from README): `data/acousticbrainz.db` (~4GB)

**New file: `core/acousticbrainz.py`**
```python
"""
Lookup real acoustic features from AcoustBrainz offline dump.
Only runs if data/acousticbrainz.db exists.
"""
import sqlite3, os

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "acousticbrainz.db")

def lookup_mbid(mbid: str) -> dict | None:
    if not os.path.exists(_DB_PATH):
        return None
    with sqlite3.connect(_DB_PATH) as conn:
        row = conn.execute(
            "SELECT energy, danceability, valence, tempo_norm, key_strength FROM tracks WHERE mbid=?",
            (mbid,)
        ).fetchone()
    if row:
        return {"energy": row[0], "danceability": row[1], "valence": row[2],
                "tempo_norm": row[3], "key_strength": row[4], "_source": "acousticbrainz"}
    return None
```

**In `core/profile.py`:** In `build()`, after MusicBrainz MBID lookup, try AcoustBrainz:
```python
if profile.get("mbid"):
    ab = acousticbrainz.lookup_mbid(profile["mbid"])
    if ab:
        profile["audio_vector"] = [ab["energy"], ab["danceability"], ab["valence"],
                                    ab["tempo_norm"], ab["key_strength"], 0.5]
        profile["audio_vector_source"] = "acousticbrainz"
```

---

## Sprint 4 — UX to production-grade (~1 day)

---

### 4.1 — Last.fm username in-app (no .env editing)
**Current state:** Last.fm OAuth IS already in Connect page. But it requires a valid Last.fm OAuth flow. The quick win is: add a plain username field that doesn't need OAuth (public data only).

**In `pages/1_Connect.py`**, in the Last.fm section, add above the OAuth button:
```python
_lf_username_input = st.text_input(
    "Last.fm username (public listening history — no password needed)",
    value=st.session_state.get("lastfm_username", ""),
    placeholder="your_lastfm_username",
)
if _lf_username_input:
    st.session_state["lastfm_username"] = _lf_username_input
    # Write to .env so it persists
    _write_env_key("LASTFM_USERNAME", _lf_username_input)
    st.success(f"Connected as {_lf_username_input}")
```

Add `_write_env_key()` helper that safely updates `.env` without losing other keys.

---

### 4.2 — Streaming history drag-and-drop
**In `pages/1_Connect.py`**, in the Spotify section after auth:
```python
st.markdown("#### Upload listening history (optional but recommended)")
st.caption("Download from spotify.com/account → Privacy → Request data. Upload all `StreamingHistory_music_*.json` files.")
uploaded = st.file_uploader("Drop your Spotify history files here", 
                             type=["json"], accept_multiple_files=True)
if uploaded:
    import json
    dest = Path("data/streaming_history")
    dest.mkdir(exist_ok=True)
    for f in uploaded:
        (dest / f.name).write_bytes(f.read())
    st.success(f"Saved {len(uploaded)} history file(s). Will be used in next scan.")
```

---

### 4.3 — Cache UX: live time estimate on Custom Scan
**In `pages/2_Scan.py`**, after each checkbox:
```python
# Estimate total scan time based on checked options and uncached track counts
_est_mins = 1  # base re-score
if _clr_lastfm:
    _lf_uncached = _count_uncached("lastfm")
    _est_mins += max(1, (_lf_uncached * 21) // 60)
if _clr_mining:
    _est_mins += 1
if _clr_lyrics:
    _lyr_uncached = _count_uncached("lyrics")
    _est_mins += max(1, (_lyr_uncached * 25) // 6000)

st.caption(f"Estimated scan time: ~{_est_mins} min")
```

---

### 4.4 — First-run wizard
**Detect first run** in `app.py`:
```python
_first_run = not os.path.exists("outputs/.last_scan_snapshot.json") and not st.session_state.get("sp")
```

If first run, show a full-screen wizard instead of normal nav:
- Step 1: Connect Spotify (required)
- Step 2: Connect Last.fm (enter username — big signal boost)
- Step 3: Choose scan: Quick (cached, <1 min) / Full (3-10 min) / Deep (clear all, 15 min)

Wizard completes when Spotify connected + scan choice made.

---

### 4.5 — Scan depth presets (rename and clarify)
Replace the three scan buttons with proper named presets:
```
Quick Rescore     — re-score from cached data                <1 min
Fresh Scan        — re-fetch tags for new tracks, re-score   3-5 min  
Deep Scan ⚠️      — clear all caches, re-fetch everything    10-15 min
```
Deep Scan shows a warning: "This will take 10-15 minutes and clear all cached data. Your library must re-fetch everything from scratch."

---

## Sprint 5 — Release infrastructure (~1 day)

---

### 5.1 — GitHub Actions: portable zip on every tag
**New file: `.github/workflows/release.yml`**
```yaml
name: Build Windows Portable

on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Download Python embeddable
        run: |
          Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.0/python-3.12.0-embed-amd64.zip" -OutFile python-embed.zip
          Expand-Archive python-embed.zip -DestinationPath vendor/python
      
      - name: Install dependencies
        run: |
          # Setup pip for embeddable Python
          # Install all requirements into vendor/python/Lib/site-packages
          
      - name: Build zip
        run: |
          $version = "${{ github.ref_name }}"
          Compress-Archive -Path . -DestinationPath "Vibesort-$version-Windows.zip" -CompressionLevel Optimal
      
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: "Vibesort-*.zip"
          generate_release_notes: true
```

---

### 5.2 — SmartScreen: clear instructions + rename launcher
Rename `START HERE.bat` with clear copy:
- `START HERE — Double-click to open Vibesort.bat`
- Add `README_FIRST.txt` with exact SmartScreen click-through steps + screenshot

Apply for free Certum open-source code signing cert when bandwidth allows.

---

### 5.3 — Spotify extended quota application
**Requirements checklist** (all completeable now):
- [x] Working app with real results
- [ ] Privacy policy at `docs/PRIVACY.md`
- [ ] Terms of service at `docs/TERMS.md`
- [ ] Screenshot of actual results (not mockup)
- [ ] Description: "Local music mood organizer — sorts user's own library into mood playlists. No data stored externally."
- [ ] `redirect_uri` registered in Spotify dashboard

**Apply at:** developer.spotify.com → Dashboard → Request Extended Quota

---

### 5.4 — Privacy policy and terms
**`docs/PRIVACY.md`** (simple, honest):
```
Vibesort is a local application. It does not have servers. Your data does not leave your machine except for:
- API calls to Spotify (to read your library and create playlists)
- Optional: API calls to Last.fm, Deezer, MusicBrainz, Genius (to enrich track data)
- No analytics. No accounts. No tracking.
```

**`docs/TERMS.md`**: Standard MIT-style terms. Use in personal projects freely.

---

### 5.5 — CONTRIBUTING.md: community curation flywheel
The most valuable contribution: adding anchor tracks. Make this trivially easy.

**`CONTRIBUTING.md`**:
```markdown
# Contributing to Vibesort

## Adding anchor tracks (no coding required)

Anchor tracks are the heart of Vibesort. They're human-curated seeds that define 
what each mood sounds like. Anyone can add them.

1. Open `data/mood_anchors.json`
2. Find the mood you want to improve
3. Add `{"artist": "Artist Name", "title": "Track Title"}`
4. The track must: unambiguously belong to this mood AND be on Spotify
5. Submit a pull request

That's it. No build step. No tests to run. Just JSON.

## Mood submissions

New mood? Open an issue with:
- Mood name + one-line description
- 10 tracks that clearly belong
- 5 tracks that clearly don't
- What makes it different from existing moods

If we can name 10 songs without arguing, it's a mood worth adding.
```

---

## Final verification checklist

Run this before declaring each item 10/10:

```python
# Run from repo root to check all invariants
python scripts/validate_all.py
```

**`scripts/validate_all.py`** checks:
- [ ] Weights sum to 1.0
- [ ] Zero invalid genre refs in packs.json
- [ ] All moods have ≥8 expected_tags
- [ ] All moods have ≥10 anchors
- [ ] Mood names consistent across packs.json and mood_anchors.json
- [ ] No duplicate anchors within a mood
- [ ] No invented tag strings (check against Last.fm tag vocab)
- [ ] All pages importable without error
- [ ] Scoring engine: sample 10 tracks, verify scores 0.0-1.0
- [ ] Track coverage ≥50% in scan snapshot
- [ ] Zero zero-result moods
- [ ] All cache files present and <30 days old

---

## Confidence targets by sprint completion

| After | Coverage | Avg Mood Size | Semantic | Audio | UX |
|---|---|---|---|---|---|
| **Now** (pre-scan) | ~35-45%* | 40-60 | 4/10 | 2/10 | 5/10 |
| **Sprint 1** | ~50-60% | 50-70 | 4/10 | 4/10 | 7/10 |
| **Sprint 2** | ~60-70% | 60-80 | 4/10 | 4/10 | 7/10 |
| **Sprint 3** | ~70-80% | 70-90 | 8/10 | 7/10 | 7/10 |
| **Sprint 4** | ~70-80% | 70-90 | 8/10 | 7/10 | 9/10 |
| **Sprint 5** | ~70-80% | 70-90 | 8/10 | 7/10 | 10/10 |

*Coverage post-conflict_penalty fix — needs actual scan to confirm.

**Why coverage tops out at ~75-80%:** ~20-25% of any library is genuinely niche (breakcore, avant-garde, regional music with no Last.fm tags). These tracks correctly don't fit any of our 83 moods. Forcing them in would hurt quality. 75% coverage + high playlist quality is better than 90% coverage + garbage playlists.
