# Vibesort

**Your Spotify library, sorted by feeling.**

Vibesort scans your liked songs, top tracks, and saved playlists — then groups them into mood, genre, era, and artist playlists using a multi-signal scoring engine that combines audio features, genre data, and real-world human labeling extracted from public Spotify playlists.

---

## Why it exists

Most tools sort by audio features alone (energy, tempo, valence). The problem: that gives you playlists that *sound* similar but don't *feel* similar. Dark phonk and sad indie can share identical audio fingerprints but hit completely differently.

Vibesort combines three signals:

| Signal | Weight | Source |
|---|---|---|
| Audio features | 45% | Spotify API (energy, valence, danceability, tempo, acousticness) |
| Playlist context | 35% | Mines public Spotify playlists to extract human vibe labels |
| Genre | 20% | 42-genre hierarchy built from Spotify's artist tags |

The playlist mining step is the key: it searches public playlists named things like "late night drive", "gym rage", "overthinking" — checks which of your songs appear in them — and uses that as a human-labeled signal. This is how real music systems work.

---

## Features

- **40 mood presets** — Late Night Drive, Villain Arc, Phonk Season, Dissolve, Rewire, and more
- **42-genre hierarchy** — East Coast Rap, West Coast Rap, Southern Rap, Houston Rap, Midwest Rap, UK Rap, French Rap, Brazilian Phonk, Funk Carioca, and many more — mapped with 500+ rules
- **Three naming engines** — Middle-out (smart hybrid, default), Top-down (preset labels), Bottom-up (named from actual content)
- **Staging shelf** — build up a list of playlists, rename them, preview tracklists, then batch-deploy to Spotify in one click
- **Recommendations** — Spotify-suggested similar songs optionally added to any playlist
- **Genre playlists** — sorted by your library's actual genre breakdown
- **Era playlists** — by decade
- **Artist spotlights** — one playlist per artist with 8+ songs in your library
- **Language playlists** — group songs by detected language
- **Blend** — multi-user blend (supports 3+ people, genre-aware, multiple angles — better than Spotify's Blend)
- **Last.fm integration** — optional, adds full play history and listening stats
- **Taste report** — obscurity score, audio fingerprint, genre breakdown, top vibes
- **Full Spotify data export** — drop your `StreamingHistory_music_*.json` files into `data/` for complete history

---

## Setup

### 1. Get free Spotify credentials (~5 min)

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Create an app (any name, any description)
3. Under **Settings → Redirect URIs**, add: `https://localhost:8501`
4. Copy your **Client ID** and **Client Secret**

### 2. Install

**Windows:** double-click `setup.bat`

**Mac / Linux:**
```bash
bash setup.sh
```

**Manual:**
```bash
pip install -r requirements.txt
cp .env.example .env
```

### 3. Add credentials

Open `.env` and fill in:
```
SPOTIFY_CLIENT_ID=your_id_here
SPOTIFY_CLIENT_SECRET=your_secret_here
```

### 4. Run

```bash
python launch.py
```

That's it. On first launch, Vibesort automatically generates an SSL certificate and configures HTTPS — nothing else to do. A browser window opens. Click **Connect to Spotify**, authorize once, and you're in.

> **Browser warning on first open:** Your browser may show "connection not private" because the certificate is self-signed. Click **Advanced → Proceed to localhost**. This is expected and safe — the cert only works on your own machine.

---

## The flow

```
Connect to Spotify
    ↓
Scan Library  (~1–3 min first time, cached after)
    ↓
Browse Vibes / Genres / Artists
    ↓
Add playlists to Staging Shelf
Rename them · toggle recommendations · preview tracks
    ↓
Deploy All to Spotify  (one click)
```

---

## Mood presets (40 total)

| Mood | Description |
|---|---|
| Acoustic Corner | Stripped back — just the song |
| Adrenaline | Maximum output — no brakes, no ceiling |
| Afterparty | Still going at 3am but slower |
| Catharsis | Emotional release — holds the feeling you can't name |
| Dark Matter | Dense, heavy, deliberately dark |
| Deep Focus | Instrumental, minimal, locked in |
| Dissolve | Sensory overload — music you feel in your body |
| Euphoric Rave | Four-on-the-floor, lights off, peak hour |
| Feel Good Friday | Weekend energy — lighthearted and ready |
| Flex Tape | Loud, arrogant, and proud of it |
| Frequency | The kind of electronic music you feel in your ribcage |
| Golden Hour | Warm and easy — everything feels right |
| Gravity | Heavy and slow — pulls you down in a good way |
| Hard Reset | Controlled destruction — the catharsis of volume |
| Hollow | Slow, heavy, and honest — the kind of sad that sits in your chest |
| Late Night Drive | Dark, drifting, midnight energy |
| Liminal | Empty hallways, 4am airports, spaces that feel too quiet |
| Midnight Clarity | 4am realizations — when everything becomes obvious |
| Morning Ritual | Slow start — coffee, light, something good happening |
| Nerve | Anxious energy converted into forward motion |
| Nostalgia | Songs that feel like a memory |
| Open Road | Windows down, no destination, just motion |
| Overflow | Peak euphoria — everything hits at once |
| Overthinking | 3am and your brain won't stop |
| Phonk Season | Aggressive, drifting, dark — the full phonk spectrum |
| Pre-Game | Energy building — by track 3 you're already hyped |
| Pressure Drop | Every track hits harder than the last |
| Raw Emotion | Unfiltered — no polish, just feeling |
| Rewire | Post-peak — mind still moving, body slowing down |
| Signal | Clean, precise electronic — built for movement |
| Signal Lost | Somewhere between sleep and awake |
| Smoke & Mirrors | Slow, hazy, lowkey — lit in the best way |
| Soft Hours | When everything needs to be gentle |
| Storm Front | Channeled rage — controlled fury |
| Sundown | End of day ease — calm but not sad |
| Tropicana | Heat, rhythm, and movement |
| Tunnel Vision | Locked in — nothing else exists right now |
| Ultraviolet | Club R&B — sensual, expensive, and late |
| Villain Arc | Calculated, cold, dominant — this is your theme music |
| Weightless | Floating — dreamy and untethered |

---

## Full listening history (optional)

Spotify's API only exposes your top 50 tracks per time window. To unlock your complete all-time history:

1. Go to [spotify.com/account/privacy](https://www.spotify.com/account/privacy/)
2. Request **Extended streaming history** (takes up to 30 days)
3. Drop the `StreamingHistory_music_*.json` files into `data/`

See `data/HOW_TO_GET_FULL_HISTORY.md` for full steps.

---

## Last.fm (optional)

Add your Last.fm credentials to `.env` to pull full scrobble history and listening stats:
```
LASTFM_API_KEY=your_key
LASTFM_API_SECRET=your_secret
LASTFM_USERNAME=your_username
```

Get a free API key at [last.fm/api](https://www.last.fm/api).

---

## Project structure

```
Vibesort/
├── app.py                      Streamlit entry point
├── config.py                   All settings (loaded from .env)
├── run.py                      CLI fallback (original)
├── requirements.txt
├── .env.example
├── setup.bat / setup.sh        One-click install
│
├── pages/
│   ├── 1_Connect.py            Spotify OAuth login
│   ├── 2_Scan.py               Library scan with progress
│   ├── 3_Vibes.py              Mood playlists browser
│   ├── 4_Genres.py             Genre / era / language playlists
│   ├── 5_Artists.py            Artist spotlight playlists
│   ├── 6_Blend.py              Multi-user blend
│   ├── 7_Staging.py            Staging shelf + deploy
│   └── 8_Stats.py              Taste report & stats
│
├── core/
│   ├── ingest.py               Collect library from Spotify
│   ├── enrich.py               Audio features + artist genres
│   ├── genre.py                42-genre mapping, era/artist breakdowns
│   ├── playlist_mining.py      Mine public playlists for human vibe labels ← core signal
│   ├── profile.py              Unified track profiles
│   ├── mood_graph.py           Mood definitions + fuzzy matching
│   ├── namer.py                Top-down / bottom-up / middle-out naming
│   ├── scorer.py               Multi-signal scoring engine ← core
│   ├── cohesion.py             Cohesion filter + scoring
│   ├── recommend.py            Spotify recommendations
│   ├── builder.py              Create playlists in Spotify
│   ├── deploy.py               Batch deploy from staging shelf
│   ├── lastfm.py               Last.fm integration
│   ├── blend.py                Multi-user playlist blending
│   ├── language.py             Language detection for grouping
│   └── history_parser.py       Parse Spotify data export JSONs
│
├── staging/
│   └── staging.py              Persistent playlist staging shelf
│
└── data/
    ├── packs.json              40 mood preset definitions
    ├── macro_genres.json       500+ genre normalization rules
    └── HOW_TO_GET_FULL_HISTORY.md
```

---

## Complementary tools

| Tool | What it adds |
|---|---|
| [stats.fm](https://stats.fm) | Full play history, year-round Wrapped |
| [Every Noise at Once](https://everynoise.com) | Spotify's map of ~6000 genres |
| [Obscurify](https://obscurify.com) | Obscurity score + genre map |
| [Receiptify](https://receiptify.herokuapp.com) | Top tracks as a shareable receipt |
| [Icebergify](https://icebergify.com) | Mainstream → obscure iceberg chart |
| [Soundiiz](https://soundiiz.com) | Transfer playlists to other platforms |
| [Last.fm](https://last.fm) | Permanent scrobble history |

---

## Requirements

- Python 3.10+
- Free Spotify account + free Spotify Developer app (5 min setup)
- Optional: Last.fm account for extended history

---

## Contributing

PRs welcome. Good places to start:

- New mood packs in `data/packs.json` — follow the existing structure
- Better genre rules in `data/macro_genres.json` — more specific rules go higher up
- Improved playlist naming in `core/namer.py`
- UI improvements in `pages/`
