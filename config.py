"""
config.py — All settings loaded from .env
Edit .env (not this file) to change settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Shared app (PKCE) — set this so end users never need a Spotify dev account
# Get your Client ID from developer.spotify.com, paste it here, request
# Extended Quota Mode, and nobody else ever has to touch the Spotify dashboard.
VIBESORT_CLIENT_ID = os.getenv("VIBESORT_CLIENT_ID", "c9e2d0ff7cbb49b0a59ca6c3b1c150bf")

# ── User's own credentials (fallback / power users) ───────────────────────────
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "https://papakoftes.github.io/VibeSort/callback.html")

# ── Data sources ──────────────────────────────────────────────────────────────
INCLUDE_LIKED_SONGS      = True
INCLUDE_TOP_TRACKS       = True
INCLUDE_FOLLOWED_ARTISTS = True
INCLUDE_SAVED_PLAYLISTS  = True
FOLLOWED_ARTIST_TOP_N    = 3

# Paste friend playlist URLs here (Spotify removed the friend API)
FRIEND_PLAYLIST_URLS: list[str] = []

# ── Playlist generation ───────────────────────────────────────────────────────
PLAYLIST_PREFIX        = os.getenv("PLAYLIST_PREFIX", "Vibesort: ")
RECS_PER_PLAYLIST      = int(os.getenv("RECS_PER_PLAYLIST", "22"))
MAX_TRACKS_PER_PLAYLIST = int(os.getenv("MAX_TRACKS_PER_PLAYLIST", "75"))
# Target minimum tracks (library + recs) when expanding with recommendations
MIN_PLAYLIST_TOTAL     = int(os.getenv("MIN_PLAYLIST_TOTAL", "30"))
MIN_SONGS_PER_GENRE    = int(os.getenv("MIN_SONGS_PER_GENRE", "5"))
MIN_SONGS_PER_ERA      = int(os.getenv("MIN_SONGS_PER_ERA", "5"))
MIN_SONGS_PER_ARTIST   = int(os.getenv("MIN_SONGS_PER_ARTIST", "8"))
COHESION_THRESHOLD     = float(os.getenv("COHESION_THRESHOLD", "0.55"))

# When a mood has fewer than this many passing tracks, rank_tracks can relax gates (MVP pass).
MVP_MIN_PLAYLIST_SIZE  = int(os.getenv("MVP_MIN_PLAYLIST_SIZE", "22"))
ALLOW_MVP_FALLBACK     = os.getenv("ALLOW_MVP_FALLBACK", "true").lower() == "true"
# Floor for MVP pass scores (also scaled from min_score when unset in code).
MVP_SCORE_FLOOR        = float(os.getenv("MVP_SCORE_FLOOR", "0.15"))

# Scoring weights (must sum to 1.0). Override via .env or outputs/.user_model.json.
# W_METADATA_AUDIO: weight for metadata-derived proxy vectors (tags/genres/BPM heuristics).
# Defaults bias slightly toward meaning (semantic) over strict macro genre — pairs with
# cross-genre rescue in scorer.effective_genre_score.
# M3.3: W_METADATA_AUDIO raised 0.10→0.14 now that real Deezer BPM data is
# available (M2.6), making the proxy tempo dimension data-driven rather than
# heuristic.  W_TAGS/W_SEMANTIC reduced slightly to absorb the difference.
# All four weights must sum to 1.0.
W_METADATA_AUDIO   = float(os.getenv("W_METADATA_AUDIO", os.getenv("W_AUDIO", "0.15")))
W_TAGS             = float(os.getenv("W_TAGS",             "0.45"))
W_SEMANTIC         = float(os.getenv("W_SEMANTIC",         "0.22"))
W_GENRE            = float(os.getenv("W_GENRE",            "0.18"))

# When playlist mining is blocked or <10% of tracks got mined tags, scale up enrichment
# caps (AudioDB, Discogs, Last.fm, Deezer, MusicBrainz, lyrics, Musixmatch).
MINING_FALLBACK_ENRICH_MULT = float(os.getenv("MINING_FALLBACK_ENRICH_MULT", "1.65"))

# Playlist mining — conservative defaults to avoid rate limits / quota burn
PLAYLISTS_PER_SEED    = int(os.getenv("PLAYLISTS_PER_SEED", "5"))
MINING_FORCE_REFRESH  = os.getenv("MINING_FORCE_REFRESH", "false").lower() == "true"
# Max track URIs fetched per public playlist (smaller = fewer API pages)
MINING_MAX_TRACKS_PER_PLAYLIST = int(os.getenv("MINING_MAX_TRACKS_PER_PLAYLIST", "100"))
# Hard cap on playlist_items calls per full mining run (stops early; cache still saves)
MINING_MAX_PLAYLIST_ITEMS_CALLS = int(os.getenv("MINING_MAX_PLAYLIST_ITEMS_CALLS", "320"))
# Delays (seconds) — stay polite to Spotify search + Web API
MINING_SEARCH_DELAY = float(os.getenv("MINING_SEARCH_DELAY", "0.38"))
MINING_PLAYLIST_ITEMS_GAP = float(os.getenv("MINING_PLAYLIST_ITEMS_GAP", "0.14"))
MINING_ITEMS_BATCH_GAP = float(os.getenv("MINING_ITEMS_BATCH_GAP", "0.12"))
# Seed phrases per mood (more = wider playlist search net)
MINING_MAX_SEED_PHRASES = int(os.getenv("MINING_MAX_SEED_PHRASES", "5"))
# Max anchor playlists processed per mood
MINING_MAX_ANCHORS_PER_MOOD = int(os.getenv("MINING_MAX_ANCHORS_PER_MOOD", "6"))
# Max owned playlists to pull items from per scan
MINING_MAX_OWNED_PLAYLISTS = int(os.getenv("MINING_MAX_OWNED_PLAYLISTS", "200"))

# ── ListenBrainz ──────────────────────────────────────────────────────────────
LISTENBRAINZ_TOKEN    = os.getenv("LISTENBRAINZ_TOKEN", "")
LISTENBRAINZ_USERNAME = os.getenv("LISTENBRAINZ_USERNAME", "")

# ── Maloja (self-hosted scrobble server) ───────────────────────────────────────
# https://github.com/krateng/maloja — run your own Last.fm alternative.
# MALOJA_URL: full base URL of your Maloja server (e.g. http://localhost:42010)
# MALOJA_TOKEN: API token from Maloja admin → Settings → API Key
MALOJA_URL   = os.getenv("MALOJA_URL",   "")
MALOJA_TOKEN = os.getenv("MALOJA_TOKEN", "")

# ── Last.fm ────────────────────────────────────────────────────────────────────
# VIBESORT_LASTFM_API_KEY / SECRET — shared Vibesort app credentials.
# Register once at https://www.last.fm/api/account/create, paste here.
# End users will see a "Connect with Last.fm" button and never need their own key.
VIBESORT_LASTFM_API_KEY    = os.getenv("VIBESORT_LASTFM_API_KEY",    "bc42469eca89948643d4404101f51666")
VIBESORT_LASTFM_API_SECRET = os.getenv("VIBESORT_LASTFM_API_SECRET", "c0821c213e0408c2e9353f514fd56d3b")

# Per-user overrides (advanced / manual setup, rarely needed)
LASTFM_API_KEY    = os.getenv("LASTFM_API_KEY",    "")
LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET", "")
LASTFM_USERNAME   = os.getenv("LASTFM_USERNAME",   "")

# ── Musixmatch (per-track genre enrichment, free tier: 2000 calls/day) ────────
MUSIXMATCH_API_KEY = os.getenv("MUSIXMATCH_API_KEY", "")
DISCOGS_TOKEN      = os.getenv("DISCOGS_TOKEN", "")        # optional — raises rate limit 25→60 req/min

# ── Genius ─────────────────────────────────────────────────────────────────────
GENIUS_API_KEY = os.getenv("GENIUS_API_KEY", "")

# ── Bandcamp ────────────────────────────────────────────────────────────────────
# Your Bandcamp username (the one in bandcamp.com/username).
# Collection must be public (or use session cookies — not yet supported).
BANDCAMP_USERNAME = os.getenv("BANDCAMP_USERNAME", "")

# ── beets music library ─────────────────────────────────────────────────────────
# Absolute path to your beets library.db SQLite file.
# Defaults to ~/.config/beets/library.db if not set.
BEETS_DB_PATH = os.getenv("BEETS_DB_PATH", "")

# ── Rate Your Music export ──────────────────────────────────────────────────────
# Absolute path to your RYM ratings/collection CSV export file.
# Export from: rateyourmusic.com → Profile → Export Data
RYM_EXPORT_PATH = os.getenv("RYM_EXPORT_PATH", "")

# ── AcoustID / Chromaprint ──────────────────────────────────────────────────────
# Free API key at acoustid.org/login — used for fingerprinting local music files.
ACOUSTID_API_KEY  = os.getenv("ACOUSTID_API_KEY", "")
# Path to fpcalc binary (optional; auto-detected from PATH if not set).
FPCALC_PATH       = os.getenv("FPCALC_PATH", "")
# Root directory of local music files to fingerprint (optional).
LOCAL_MUSIC_PATH  = os.getenv("LOCAL_MUSIC_PATH", "")

# ── MusicBrainz ───────────────────────────────────────────────────────────────
MUSICBRAINZ_ENRICH = os.getenv("MUSICBRAINZ_ENRICH", "false").lower() == "true"

# Max tracks from the same artist in any generated playlist (default 3).
# Lower = more diverse; higher = allows deep-dives into one artist.
MAX_TRACKS_PER_ARTIST = int(os.getenv("MAX_TRACKS_PER_ARTIST", "4"))

# ── Navidrome / Jellyfin (OpenSubsonic API) ────────────────────────────────────
# https://www.navidrome.org/ — starred tracks + local genre tags.
# Both Navidrome and Jellyfin (with OpenSubsonic plugin) are supported.
NAVIDROME_URL  = os.getenv("NAVIDROME_URL",  "")
NAVIDROME_USER = os.getenv("NAVIDROME_USER", "")
NAVIDROME_PASS = os.getenv("NAVIDROME_PASS", "")

# ── Apple Music ───────────────────────────────────────────────────────────────
# Path to your Apple Music / iTunes Library XML export.
# In Apple Music: File → Library → Export Library... → save the .xml file.
# Defaults to ~/Music/Music/Music Library.xml if not set.
APPLE_MUSIC_XML_PATH = os.getenv("APPLE_MUSIC_XML_PATH", "")

# ── Plex Media Server ─────────────────────────────────────────────────────────
# https://www.plex.tv/ — rated/played tracks + local genre tags.
# PLEX_URL: full base URL (e.g. http://localhost:32400)
# PLEX_TOKEN: Settings → Troubleshooting → "Download logs" → search X-Plex-Token
PLEX_URL   = os.getenv("PLEX_URL",   "")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")

# Staging
STAGING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "staging", "playlists")
