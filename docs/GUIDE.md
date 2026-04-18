# Vibesort — Getting Started Guide

> **New here?** This document walks you through everything from first launch to deploying your first playlists to Spotify.

---

## What is Vibesort?

Vibesort is a local app that scans your Spotify library and organizes it into playlists by **mood, genre, era, and artist** — using a multi-signal scoring engine rather than raw audio features. The core insight: a song's *feel* comes from tags, genre context, lyric themes, and how real humans playlist it, not just its BPM or energy level.

All processing happens on your machine. Nothing is sent to a server.

---

## 1. Installation

### Windows

1. Download or clone this repository
2. Double-click **`run.bat`**

That's it. On first launch it checks for Python 3.10+, installs all Python dependencies, and opens the app in your browser. If Python isn't installed, it opens the download page for you.

### Mac

Double-click **`Vibesort.command`** in Finder. If macOS blocks it: right-click → Open → Open anyway (one-time only).

Or in Terminal:

```bash
bash run.sh
```

### Linux

```bash
bash run.sh
```

Same auto-setup behavior on all platforms.

### Manual

```bash
python launch.py
```

---

## 2. Connect to Spotify

When the app opens, you'll land on the **Connect** page.

<p align="center">
  <img src="screenshots/connect.png" alt="Connect page" width="700"/>
</p>

Click **Connect to Spotify**. Your browser will open Spotify's authorization page. Log in, click **Agree**, and you'll be redirected back. The app reads your token automatically — no copy-pasting.

> **Dev Mode note:** The shared app has a 25-user limit (Spotify policy). If you see "access denied", use your own free Spotify developer app: create one at [developer.spotify.com](https://developer.spotify.com), add `https://papakoftes.github.io/VibeSort/callback.html` as a Redirect URI, and paste the Client ID into the Settings page. No client secret needed.

---

## 3. Scan Your Library

Go to **Scan** in the sidebar (or click the button on the Connect page).

<p align="center">
  <img src="screenshots/scan.png" alt="Scan page" width="700"/>
</p>

**Scan modes (Scan page):**
- **Full scan** — full library corpus (liked songs, followed artists, top tracks, saved playlists where enabled)
- **Custom scan** — refresh selected enrichment caches only (mining, lyrics, Last.fm, …)
- **Local library** — optional Chromaprint / AcoustID fingerprinting for files under `LOCAL_MUSIC_PATH`

Click **Scan Library**. The first scan takes **about 3–15 minutes** depending on library size and caches. It:
1. Fetches your tracks from Spotify
2. Pulls genre tags from MusicBrainz and Last.fm (and optional sources you enabled)
3. Mines public Spotify playlists when the API allows — in Spotify Development Mode this may be limited; enrichment backfills from other sources
4. Builds profiles for every track combining genres, tags, lyrics, and metadata-derived signals (Spotify audio-features are not available for third-party apps)
5. Runs each track through **110** mood scorers (see `data/packs.json`)
6. Writes caches under `outputs/` so re-scans are much faster

After scanning, the results are cached — future launches load in under a second.

---

## 4. Browse Your Vibes

Open **Vibes** in the sidebar.

<p align="center">
  <img src="screenshots/vibes.png" alt="Vibes page" width="700"/>
</p>

You'll see mood playlist cards sorted by match quality (how strongly your tracks fit that vibe). Each card shows:
- The mood name and description
- Track count + match quality label (Perfect fit / Great fit / Good fit / Mixed / Broad)
- Signal badges for each track (curated anchor · personal · similarity · Last.fm · lyrics)
- Insight lines: how many tracks you personally return to, how many were found via similarity graph

**Filter** by tag (e.g. `dark`, `lo-fi`, `rap`) or sort by match quality/size.

Click **Build Playlist** on a card to stage that mood for review. Open **Staging** in the sidebar (some buttons still say “Playlist Queue”) to rename, preview, and deploy.

---

## 5. Browse by Genre, Artist, or Era

The sidebar has dedicated pages for each dimension:

- **Genres** — 42-genre hierarchy (East Coast Rap, Synthwave, Folk/Americana, etc.). Filter by family (Genre / Decade / Language / Tempo / BPM / Sound Character).
- **Artists** — One playlist per artist with 8+ songs in your library
- **Taste Map** — Visual cluster map of your library in 2D mood-space

---

## 6. Staging (playlist queue)

<p align="center">
  <img src="screenshots/staging.png" alt="Staging shelf — rename, preview, deploy" width="700"/>
</p>

**Staging** is your shelf before playlists exist in Spotify. Here you can:
- **Rename** any playlist before it's created
- **Preview** the full tracklist
- Toggle **Spotify Recommendations** to pad a playlist with similar tracks Spotify suggests
- Remove playlists you've changed your mind about
- Click **Deploy All** to create everything in one shot

Deployed playlists appear in your Spotify account immediately.

---

## 7. Your Taste Report

Open **Stats** to see a breakdown of your library.

<p align="center">
  <img src="screenshots/stats.png" alt="Stats / Taste Report" width="700"/>
</p>

Includes:
- Track count, unique artists, genres, eras, moods detected
- **Obscurity score** (0–100, higher = more underground)
- Genre breakdown chart
- Era distribution
- Top detected moods and their cohesion
- Audio fingerprint (energy, valence, danceability, tempo, acousticness, instrumentalness)
- Top artists by library count
- Vibe tag cloud
- Enrichment coverage (how much signal was collected per track)

---

## 8. Optional Enrichment

### Last.fm

Adds your full scrobble history as a listening-weight signal. Go to **Connect** and enter your Last.fm username (no API key needed — the app ships with a shared key).

### ListenBrainz

Open-source scrobble history. Same flow: go to **Connect**, paste your ListenBrainz token and username.

### Full Spotify History

Spotify's API only returns your top 50 tracks per time window. To unlock your *complete* all-time play history:

1. Go to [spotify.com/account/privacy](https://www.spotify.com/account/privacy/)
2. Request **Extended streaming history** (takes up to 30 days to receive)
3. Drop the `StreamingHistory_music_*.json` files into the `data/` folder
4. Launch Vibesort and run **Scan Library** so files in `data/` are picked up

### Discogs

Adds genre and style tags from Discogs releases. Enable in **Settings → Enrichment Sources**.

---

## 9. Settings Reference

Open **Settings** in the sidebar.

<p align="center">
  <img src="screenshots/settings.png" alt="Settings page" width="700"/>
</p>

| Section | What it controls |
|---|---|
| **Connections** | Manage Spotify, Last.fm, ListenBrainz credentials |
| **Playlist generation** | Scoring strictness, expansion fallback, MVP mood filter |
| **Enrichment sources** | Toggle MusicBrainz, Last.fm tags, AudioDB, Discogs, lyrics |
| **Quick tests** | Test each API connection instantly |
| **Playlist defaults** | Default size, naming engine, description format |
| **.env template** | Copy a starter config file for manual setup |
| **Cache management** | Clear scan cache, reset all data |

---

## 10. Blend (Multi-user)

The **Blend** page lets multiple people merge their libraries for a shared playlist. Supports 3+ users, genre-aware weighting, and multiple "angles" (shared taste vs. compromise vs. discovery). Each user connects their own Spotify account.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Please connect to Spotify first" on all pages | Go to Connect and click **Connect to Spotify** |
| Scan hangs at playlist mining | Normal — enrichment can take several minutes on first scan. Subsequent scans use cache and are much faster. |
| Too many songs in "Other" genre | Re-scan after adding Last.fm or genre tags — the backfill improves classification |
| App won't start (Windows) | Make sure Python 3.10+ is on PATH and `run.bat` was used |
| Port 8501 already in use | Another Streamlit app is running. Close it or set `STREAMLIT_PORT` in `.env` |
| Spotify "access denied" | The shared app has a 25-user limit. Use your own free Spotify developer app — takes 5 minutes. See the Connect page for instructions. |

---

## File Layout Reference

```
Vibesort/
├── run.bat / run.sh         Double-click to launch
├── launch.py                Dependency check + Streamlit starter
├── app.py                   Sidebar + home page
├── config.py                All settings (reads from .env)
│
├── pages/
│   ├── 1_Connect.py         Spotify / Last.fm / ListenBrainz auth
│   ├── 2_Scan.py            Library scan trigger + progress
│   ├── 3_Vibes.py           Mood playlist browser
│   ├── 4_Genres.py          Genre playlist browser
│   ├── 5_Artists.py         Artist playlist browser
│   ├── 6_Taste_Map.py       2D cluster visualization
│   ├── 7_Blend.py           Multi-user blend
│   ├── 8_Stats.py           Taste report + charts
│   └── 9_Settings.py        All settings
│
├── core/
│   ├── scan_pipeline.py     Orchestrates the full scan
│   ├── ingest.py            Spotify API calls + caching
│   ├── enrich.py            MusicBrainz, Last.fm, AudioDB enrichment
│   ├── playlist_mining.py   Public playlist tag mining
│   ├── scorer.py            Multi-signal mood scoring engine
│   ├── profile.py           Per-track signal profiles
│   ├── genre.py             Genre normalization (42 macro genres)
│   ├── deploy.py            Spotify playlist creation
│   └── theme.py             App CSS / design tokens
│
└── data/
    ├── packs.json           110 mood preset definitions
    ├── macro_genres.json    500+ genre normalization rules
    └── HOW_TO_GET_FULL_HISTORY.md
```

---

## Contributing

- **New moods** — add entries to `data/packs.json` under `"moods"`. Follow the existing structure (name, description, semantic_core, tags, genre_hints, audio_hint).
- **Better genre rules** — edit `data/macro_genres.json`. More specific rules go higher in the list (first match wins).
- **Bug reports** — open an issue on GitHub.
- **Pull requests** — welcome for any of the above, plus UI improvements in `pages/`.
