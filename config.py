"""
config.py — All settings loaded from .env
Edit .env (not this file) to change settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Required ──────────────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8501")

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
RECS_PER_PLAYLIST      = int(os.getenv("RECS_PER_PLAYLIST", "15"))
MAX_TRACKS_PER_PLAYLIST = int(os.getenv("MAX_TRACKS_PER_PLAYLIST", "50"))
MIN_SONGS_PER_GENRE    = int(os.getenv("MIN_SONGS_PER_GENRE", "5"))
MIN_SONGS_PER_ERA      = int(os.getenv("MIN_SONGS_PER_ERA", "5"))
MIN_SONGS_PER_ARTIST   = int(os.getenv("MIN_SONGS_PER_ARTIST", "8"))
COHESION_THRESHOLD     = float(os.getenv("COHESION_THRESHOLD", "0.60"))

# Scoring weights (must roughly sum to 1.0)
W_AUDIO = float(os.getenv("W_AUDIO", "0.45"))
W_TAGS  = float(os.getenv("W_TAGS",  "0.35"))
W_GENRE = float(os.getenv("W_GENRE", "0.20"))

# Playlist mining settings
PLAYLISTS_PER_SEED    = int(os.getenv("PLAYLISTS_PER_SEED", "4"))
MINING_FORCE_REFRESH  = os.getenv("MINING_FORCE_REFRESH", "false").lower() == "true"

# ── ListenBrainz ──────────────────────────────────────────────────────────────
LISTENBRAINZ_TOKEN    = os.getenv("LISTENBRAINZ_TOKEN", "")
LISTENBRAINZ_USERNAME = os.getenv("LISTENBRAINZ_USERNAME", "")

# ── Genius ─────────────────────────────────────────────────────────────────────
GENIUS_API_KEY = os.getenv("GENIUS_API_KEY", "")

# ── MusicBrainz ───────────────────────────────────────────────────────────────
MUSICBRAINZ_ENRICH = os.getenv("MUSICBRAINZ_ENRICH", "false").lower() == "true"

# Staging
STAGING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "staging", "playlists")
