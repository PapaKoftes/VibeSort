# Vibesort 🎧

> *Your music library, finally sorted by feeling.*

<p align="center">
  <img src="docs/screenshots/home.png" alt="Vibesort home screen" width="800"/>
</p>

You know that feeling when a song hits exactly right for the moment? Vibesort is built around that. It reads your Spotify library and sorts everything into **87 mood playlists** — not by BPM or energy level, but by what the music actually *feels* like. Hollow for 3am existential spirals. Villain Arc for when you need to feel unstoppable. Late Night Drive for exactly what it sounds like.

---

## Get started

**Windows:** double-click `run.bat`  
**Mac / Linux:** `bash run.sh`  
**Or:** `python launch.py` (Python 3.10+ required)

First launch installs dependencies and opens in your browser. Click **Connect to Spotify**, authorize, done.

Step-by-step install: **[SETUP.md](SETUP.md)**  
Full guide: **[docs/GUIDE.md](docs/GUIDE.md)**

> **Dev Mode note:** The app runs in Spotify Development Mode (25-user limit). If you can't connect, [open an issue](https://github.com/PapaKoftes/VibeSort/issues) to be added.

---

## How it works

Vibesort uses a multi-signal scoring engine — not just one data source, but five layered together:

| Signal | Weight | What it catches |
|--------|--------|-----------------|
| Tags | 48% | Playlist mining, Last.fm, lyrics, Deezer, Discogs |
| Semantic | 22% | Abstract vibe matching |
| Genre | 20% | 42-genre hierarchy with 500+ mapping rules |
| Metadata proxy | 10% | BPM, energy, tempo heuristics |

**Spotify killed their audio-features API in late 2024.** Vibesort routes around it via three ground-truth pillars:
1. **87 curated mood anchors** — 3–5 hand-picked seed tracks per mood that inject the strongest possible signal when found in your library
2. **Last.fm similarity graph** — BFS propagation through your library using track similarity data
3. **Last.fm tag chart mining** — crowd-sourced mood tags from millions of listeners

---

## What you get

- **87 mood playlists** — Hollow, Villain Arc, Late Night Drive, Phonk Season, Rewire, Dissolve, and 81 more
- **42 genre playlists** — mapped with 500+ rules (East Coast Rap, UK Rap, Brazilian Phonk, Funk Carioca, etc.)
- **Era playlists** — by decade
- **Artist spotlights** — one playlist per artist with 8+ songs in your library
- **Emotional Fingerprint** — a visual breakdown of your library's emotional DNA (DARK / POWER / CHILL / PARTY / STORY)
- **Mood Atlas** — see all 87 moods and which ones are missing from your library (with discovery suggestions)
- **Taste Map** — explore your library's clusters visually
- **Staging shelf** — queue playlists, rename them, preview tracks, then batch-deploy to Spotify in one click
- **Blend** — multi-user blend, genre-aware, better than Spotify's (supports 3+ people)
- **Last.fm integration** — play history, personal listening anchors, time-of-day tags

---

## The flow

```
Connect to Spotify
    ↓
Scan Library  (~1–3 min first time)
    ↓
Browse Vibes · Genres · Artists
    ↓
Staging Shelf  (rename · preview · toggle recommendations)
    ↓
Deploy All → Spotify  (one click)
```

<p align="center">
  <img src="docs/screenshots/scan.png" alt="Library Scan page" width="800"/>
</p>

---

## Optional: Last.fm

Add your key to `.env` for richer mood matching and personal anchor seeding:

```
LASTFM_API_KEY=your_key
LASTFM_API_SECRET=your_secret  
LASTFM_USERNAME=your_username
```

Free key at [last.fm/api](https://www.last.fm/api). With Last.fm connected, your most-played tracks get promoted to **personal anchors** — they pull their moods harder because the data proves you actually listen to them.

---

## Optional: your own Spotify app

```
VIBESORT_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
```

Register `https://papakoftes.github.io/VibeSort/callback.html` as your redirect URI.

---

## Project layout

```
Vibesort/
├── app.py              Home + routing
├── config.py           Settings (.env)
├── launch.py           Entrypoint
├── run.bat / run.sh    User launchers
│
├── pages/              Streamlit UI (Connect, Scan, Vibes, Genres, …)
├── core/               Scoring engine, enrichers, integrations
├── staging/            Playlist staging + deploy
├── tests/              60+ unit tests + audit script
│
└── data/
    ├── packs.json          87 mood definitions
    ├── mood_anchors.json   361 curated seed tracks
    └── macro_genres.json   Genre mapping rules
```

---

## Requirements

- Python 3.10+
- Free Spotify account
- Optional: Last.fm account

---

## Contributing

PRs welcome. Good places to start:
- New mood packs in `data/packs.json`
- Better genre rules in `data/macro_genres.json`
- Improved playlist naming in `core/namer.py`
- UI improvements in `pages/`

---

<p align="center">
  <img src="docs/screenshots/vibes.png" alt="Vibes page showing mood playlist cards" width="800"/>
</p>

<p align="center">
  <img src="docs/screenshots/genres.png" alt="Genre Playlists" width="390" style="display:inline-block; margin-right:8px"/>
  <img src="docs/screenshots/stats.png" alt="Taste Report / Stats" width="390" style="display:inline-block"/>
</p>

---

## Related tools

| Tool | What it adds |
|------|-------------|
| [Last.fm](https://last.fm) | Permanent scrobble history |
| [stats.fm](https://stats.fm) | Full play history |
| [Every Noise at Once](https://everynoise.com) | Spotify's map of ~6000 genres |
| [Obscurify](https://obscurify.com) | Obscurity score |
| [Soundiiz](https://soundiiz.com) | Transfer playlists between platforms |
