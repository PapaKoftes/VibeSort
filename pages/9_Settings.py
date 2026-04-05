"""
pages/9_Settings.py — Vibesort Settings & Configuration.

Shows which API keys and data sources are active, with instructions
for enabling each one.  All settings live in the .env file — this page
is read-only (for security) but gives clear copy-paste instructions.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort — Settings",
    page_icon="⚙️",
    layout="wide",
)
from core.theme import inject
inject()

import config as cfg

# ── Helpers ───────────────────────────────────────────────────────────────────

def _dot(ok: bool, label_ok: str, label_no: str) -> str:
    return f"{'🟢' if ok else '🔴'} **{label_ok if ok else label_no}**"


def _key_status(value: str) -> str:
    if not value:
        return "❌ not set"
    masked = value[:4] + "•" * min(len(value) - 4, 12) + value[-2:] if len(value) > 6 else "•••"
    return f"✅ configured ({masked})"


# ── Load current values ───────────────────────────────────────────────────────

sp_token      = bool(st.session_state.get("spotify_token"))
lf_key        = getattr(cfg, "LASTFM_API_KEY",       "").strip()
lb_token      = getattr(cfg, "LISTENBRAINZ_TOKEN",   "").strip()
lb_user       = getattr(cfg, "LISTENBRAINZ_USERNAME", "").strip()

# ── Page ──────────────────────────────────────────────────────────────────────

st.title("⚙️ Settings")
st.caption("All settings are loaded from your `.env` file. Edit that file and restart the app to apply changes.")

# ─────────────────────────────────────────────────────────────────────────────
# Playlist first (most users tweak these every session)
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## Playlist generation")
st.caption("Tune how playlists are built from your scored tracks (saved in this browser session).")

strictness = st.slider(
    "Scoring strictness",
    min_value=1, max_value=5, value=int(st.session_state.get("strictness", 3)),
    help="Higher = stricter cohesion trim, stronger refine pass, and higher score floor",
)
st.session_state["strictness"] = strictness
min_score = 0.15 + (strictness - 1) * 0.05
st.session_state["playlist_min_score"] = min_score

min_playlist_size = st.number_input(
    "Minimum tracks per playlist",
    min_value=5, max_value=50, value=int(st.session_state.get("playlist_min_size", 20)), step=5,
)
st.session_state["playlist_min_size"] = min_playlist_size

expansion_enabled = st.toggle(
    "Enable expansion fallback",
    value=bool(st.session_state.get("playlist_expansion", True)),
    help="When enabled, thin playlists are backfilled with lower-scoring tracks to reach minimum size",
)
st.session_state["playlist_expansion"] = expansion_enabled

mvp_enabled = st.toggle(
    "Allow MVP fallback for thin moods",
    value=bool(st.session_state.get("allow_mvp_fallback", getattr(cfg, "ALLOW_MVP_FALLBACK", True))),
    help="When off, moods with fewer than the MVP threshold tracks stay strict (may yield very short or empty playlists)",
)
st.session_state["allow_mvp_fallback"] = mvp_enabled

st.divider()
st.markdown("## Playlist defaults (`.env`)")
st.caption("Server-side caps and prefixes — edit `.env` and restart the app.")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**Current values**")
    settings = {
        "PLAYLIST_PREFIX":         getattr(cfg, "PLAYLIST_PREFIX", "Vibesort: "),
        "MAX_TRACKS_PER_PLAYLIST": getattr(cfg, "MAX_TRACKS_PER_PLAYLIST", 50),
        "MIN_SONGS_PER_GENRE":     getattr(cfg, "MIN_SONGS_PER_GENRE", 5),
        "MIN_SONGS_PER_ARTIST":    getattr(cfg, "MIN_SONGS_PER_ARTIST", 8),
        "COHESION_THRESHOLD":      getattr(cfg, "COHESION_THRESHOLD", 0.60),
        "W_AUDIO":                 getattr(cfg, "W_AUDIO", 0.0),
        "W_METADATA_AUDIO":        getattr(cfg, "W_METADATA_AUDIO", 0.10),
        "W_TAGS":                  getattr(cfg, "W_TAGS", 0.48),
        "W_SEMANTIC":              getattr(cfg, "W_SEMANTIC", 0.22),
        "W_GENRE":                 getattr(cfg, "W_GENRE", 0.20),
        "ALLOW_MVP_FALLBACK":      getattr(cfg, "ALLOW_MVP_FALLBACK", True),
        "MVP_MIN_PLAYLIST_SIZE":    getattr(cfg, "MVP_MIN_PLAYLIST_SIZE", 15),
        "MVP_SCORE_FLOOR":          getattr(cfg, "MVP_SCORE_FLOOR", 0.15),
    }
    for k, v in settings.items():
        st.code(f"{k}={v}", language="bash")

with col_b:
    st.markdown("**What they do**")
    st.markdown(
        """
        - `PLAYLIST_PREFIX` — prefix added to all deployed playlist names
        - `MAX_TRACKS_PER_PLAYLIST` — cap per mood/genre playlist
        - `MIN_SONGS_PER_GENRE` — min tracks for a genre playlist to appear
        - `MIN_SONGS_PER_ARTIST` — min tracks for an artist spotlight
        - `COHESION_THRESHOLD` — baseline for audio outlier pass (scan also uses tag/semantic cohesion)
        - `W_AUDIO` — Spotify API audio (locked 0); `W_METADATA_AUDIO` — weight for tags/genres-derived proxy vectors; `W_TAGS` / `W_SEMANTIC` / `W_GENRE` — must sum with `W_METADATA_AUDIO` to 1.0 for default tuning
        - `ALLOW_MVP_FALLBACK` — allow relaxed scoring when a mood has very few matches
        - `MVP_MIN_PLAYLIST_SIZE` / `MVP_SCORE_FLOOR` — MVP pass trigger and floor
        """
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Connection
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## Spotify")

col_info, col_action = st.columns([3, 1])
with col_info:
    if sp_token:
        user = st.session_state.get("me", {})
        uname = user.get("display_name", "Unknown")
        st.success(f"✅ Connected as **{uname}**")
    else:
        st.error("❌ Not connected")

with col_action:
    if not sp_token:
        if st.button("Connect →", use_container_width=True, type="primary"):
            st.switch_page("pages/1_Connect.py")
    else:
        if st.button("Disconnect", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.switch_page("pages/1_Connect.py")

with st.expander("Spotify Dev Mode limitations & how to fix them"):
    st.markdown(
        """
        In **Development Mode** (the default for new Spotify apps) several endpoints are restricted:

        | Endpoint | Status | Workaround active |
        |---|---|---|
        | `GET /audio-features` | ❌ Deprecated Nov 2024 — gone for everyone | AudioDB `intBPM` (partial) |
        | `GET /artists?ids=` | ❌ 403 in Dev Mode | `/v1/search` fallback ✅ |
        | `GET /playlists/{id}/items` | ❌ 403 for all playlists | Last.fm / Deezer / AudioDB ✅ |
        | `GET /me/following/contains` | ❌ 403 in Dev Mode | Not needed for core flow |

        **Permanent fix**: Apply for [Extended Quota Mode](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)
        on your Spotify developer dashboard — this removes the 403 restrictions on batch artists
        and playlist items, giving you full playlist mining.

        **Note**: Audio features (`energy`, `valence`, `tempo`, etc.) are permanently removed
        from the Spotify API and will **not** return with Extended Quota Mode. Vibesort uses
        tag-based and genre-based scoring instead.
        """
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Enrichment sources
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## Enrichment Sources")
st.caption("These determine how well Vibesort can match tracks to moods and genres.")

# ── Deezer ────────────────────────────────────────────────────────────────────
with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### 🟢 Deezer  ·  Genre enrichment")
        st.markdown("Built-in · No API key required · Always active")
        st.caption(
            "Fetches genre data (Rap/Hip Hop, R&B, Electronic, etc.) for your artists "
            "by searching Deezer's public API. Works out of the box with zero setup. "
            "Cached after the first scan."
        )
    with c2:
        st.success("Built-in")

    try:
        from core.deezer import cache_stats as _dz_cache
        stats = _dz_cache()
        n_cached = stats.get("artists_cached", 0)
        if n_cached:
            st.caption(f"Cache: {n_cached} artists stored")
    except Exception:
        pass

# ── TheAudioDB ────────────────────────────────────────────────────────────────
with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### 🟢 TheAudioDB  ·  Artist & track mood/genre labels")
        st.markdown("Built-in · No API key required · Always active")
        st.caption(
            "Editorial-quality mood, genre, and style labels per artist AND per track. "
            "Unlike Deezer (genres only), AudioDB provides direct mood labels like "
            "'Dark', 'Melancholic', 'Energetic' that feed straight into mood scoring. "
            "Artist mood data broadcasts to all tracks by that artist for broad coverage. "
            "Cached after the first scan (~90s)."
        )
    with c2:
        st.success("Built-in")

    try:
        from core.audiodb import cache_stats as _adb_cache
        _adb_stats = _adb_cache()
        _adb_n = _adb_stats.get("artists_cached", 0) + _adb_stats.get("tracks_cached", 0)
        if _adb_n:
            st.caption(
                f"Cache: {_adb_stats.get('artists_cached', 0)} artists · "
                f"{_adb_stats.get('tracks_cached', 0)} tracks"
            )
    except Exception:
        pass

# ── Discogs ───────────────────────────────────────────────────────────────────
with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### 🟢 Discogs  ·  Sub-genre styles")
        st.markdown("Built-in · No key required · Always active")
        st.caption(
            "Adds precise style labels (Cloud Rap, Shoegaze, Trip-Hop, Neo Soul, Grunge, …) "
            "that Deezer’s broad genres miss. Styles feed mood tags and macro-genre mapping; "
            "they also improve tempo-band inference on the Genres page. "
            "Optional `DISCOGS_TOKEN` in `.env` raises the API rate limit from 25 to 60 req/min."
        )
    with c2:
        st.success("Built-in")

    try:
        from core.discogs import _load_cache as _dc_load
        _dc_raw = _dc_load()
        _dc_n = len(_dc_raw.get("artists", {}))
        if _dc_n:
            st.caption(f"Cache: {_dc_n} artists stored")
    except Exception:
        pass

# ── Musixmatch ────────────────────────────────────────────────────────────────
_mx_key = getattr(cfg, "MUSIXMATCH_API_KEY", "").strip()
with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### Musixmatch  ·  Per-track genre tags")
        st.markdown("Optional · Free API key · Trusted (used by Apple Music, Amazon Music)")
        st.caption(
            "Provides per-track genre classification from the world's largest licensed lyrics "
            "database. Uses ISRC codes for exact track matching — no wrong-artist false matches. "
            "Free tier: 2,000 API calls/day. Cached after first scan so subsequent runs "
            "cost zero calls."
        )
        st.code("MUSIXMATCH_API_KEY=your_key_here", language="bash")
        st.markdown("[Get a free key at developer.musixmatch.com →](https://developer.musixmatch.com/)")
    with c2:
        if _mx_key:
            st.success("Active")
        else:
            st.info("Not set")
    st.caption(f"Status: {_key_status(_mx_key)}")
    try:
        from core.musixmatch import cache_stats as _mx_cache
        _mx_stats = _mx_cache()
        _mx_n = _mx_stats.get("tracks_cached", 0)
        if _mx_n:
            st.caption(f"Cache: {_mx_n} tracks stored")
    except Exception:
        pass

# ── Last.fm ───────────────────────────────────────────────────────────────────
with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### Last.fm  ·  Artist genre + track mood tags")
        st.markdown("Optional · Free API key · **Strongly recommended**")
        st.caption(
            "Crowd-sourced genre and mood tags per artist AND per track. "
            "Significantly improves mood playlist quality — tags like 'sad', 'dark', "
            "'chill', 'hype' go directly into the scoring engine."
        )
        st.code("LASTFM_API_KEY=your_key_here", language="bash")
        st.markdown("[Get a free key at last.fm/api/account/create →](https://www.last.fm/api/account/create)")
    with c2:
        if lf_key:
            st.success("Active")
        else:
            st.warning("Not set")
    st.caption(f"Status: {_key_status(lf_key)}")

# ── Lyrics (built-in) ─────────────────────────────────────────────────────────
with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### Lyrics  ·  Lyrical mood analysis")
        st.markdown(
            "Built-in · [lrclib.net](https://lrclib.net) + [lyrics.ovh](https://lyrics.ovh) · "
            "optional [Genius](https://genius.com) fallback"
        )
        st.caption(
            "Fetches lyrics during each scan and scores mood keywords (sad, dark, angry, love, "
            "hype, introspective, euphoric, party). Results are cached in `.lyrics_cache.json`. "
            "Add a free Genius API key for extra coverage when the open sources miss a track."
        )
    with c2:
        st.success("Always on")

_genius_key = getattr(cfg, "GENIUS_API_KEY", "").strip()
with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### Genius  ·  Lyrics fallback")
        st.markdown("Optional · Free API key · Higher lyric coverage")
        st.caption(
            "Used only when lrclib and lyrics.ovh return no lyrics. Cached separately in "
            "`.genius_cache.json` (successful fetches only)."
        )
        st.code("GENIUS_API_KEY=your_key_here", language="bash")
        st.markdown("[Create an API client at genius.com/api-clients →](https://genius.com/api-clients)")
    with c2:
        if _genius_key:
            st.success("Active")
        else:
            st.info("Not set")
    st.caption(f"Status: {_key_status(_genius_key)}")

# ── ListenBrainz ──────────────────────────────────────────────────────────────
with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### ListenBrainz  ·  Listening history")
        st.markdown("Optional · Free · Requires ListenBrainz account")
        st.caption(
            "Uses your personal listening history to boost frequently-played tracks "
            "in mood playlists. Tracks in your top 100 most-listened get a small "
            "score multiplier (up to 1.2×) so songs you already love rank higher "
            "within any mood they qualify for. Requires liblistenbrainz: "
            "`pip install liblistenbrainz`."
        )
        st.code(
            "LISTENBRAINZ_TOKEN=your_token\nLISTENBRAINZ_USERNAME=your_username",
            language="bash",
        )
        st.markdown("[Sign up at listenbrainz.org →](https://listenbrainz.org)")
    with c2:
        if lb_token:
            st.success("Active")
        else:
            st.info("Not set")
    if lb_user:
        st.caption(f"Username: {lb_user}")

st.divider()
st.markdown("### Quick connection tests")
st.caption("Minimal API probes using keys from `.env`. Restart the app after editing `.env`.")

_tc1, _tc2, _tc3 = st.columns(3)
with _tc1:
    if st.button("Test Last.fm", use_container_width=True, key="probe_lastfm"):
        if lf_key:
            with st.spinner("Last.fm…"):
                from core.lastfm import get_artist_tags

                _tags = get_artist_tags("The Beatles", lf_key)
            if _tags:
                st.success(f"OK — {len(_tags)} tags for sample artist")
            else:
                st.warning("No tags returned (check key or network)")
        else:
            st.info("Add LASTFM_API_KEY first")
with _tc2:
    if st.button("Test ListenBrainz", use_container_width=True, key="probe_lb"):
        if lb_token and lb_user:
            try:
                from core import listenbrainz as _lbm

                _c = _lbm.connect(lb_token)
                st.success("Token OK") if _c else st.error("Connection failed")
            except Exception as _e:
                st.error(str(_e))
        else:
            st.info("Add LISTENBRAINZ_TOKEN and USERNAME")
with _tc3:
    if st.button("Check Genius key", use_container_width=True, key="probe_genius"):
        if _genius_key and len(_genius_key) > 16:
            st.success("Key format looks valid (no live API call)")
        elif _genius_key:
            st.warning("Key seems short — verify at genius.com/api-clients")
        else:
            st.info("Add GENIUS_API_KEY for lyrics fallback")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 4: .env template
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("## .env Template")
st.caption("Copy this into your `.env` file and fill in the keys you have.")

env_template = """\
# ── Spotify ──────────────────────────────────────────────────────────────────
# Only needed if using your own Spotify app (optional — PKCE shared app works)
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=https://papakoftes.github.io/VibeSort/callback.html

# ── Last.fm (strongly recommended — free at last.fm/api/account/create) ──────
LASTFM_API_KEY=
LASTFM_API_SECRET=
LASTFM_USERNAME=

# ── Musixmatch (recommended — free at developer.musixmatch.com) ──────────────
MUSIXMATCH_API_KEY=

# ── Genius (optional — lyrics fallback, genius.com/api-clients)
GENIUS_API_KEY=

# ── Discogs (optional token — higher rate limit, discogs.com/settings/developers)
DISCOGS_TOKEN=

# ── ListenBrainz (optional — free at listenbrainz.org) ───────────────────────
LISTENBRAINZ_TOKEN=
LISTENBRAINZ_USERNAME=

# ── Playlist settings ─────────────────────────────────────────────────────────
PLAYLIST_PREFIX=Vibesort:
MAX_TRACKS_PER_PLAYLIST=50
MIN_SONGS_PER_GENRE=5
MIN_SONGS_PER_ARTIST=8
COHESION_THRESHOLD=0.60
ALLOW_MVP_FALLBACK=true
MVP_MIN_PLAYLIST_SIZE=15
MVP_SCORE_FLOOR=0.15
"""
st.code(env_template, language="bash")

# ─────────────────────────────────────────────────────────────────────────────
# Section 5: Cache management
# ─────────────────────────────────────────────────────────────────────────────

st.divider()
st.markdown("## Cache")

_settings_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cache_files = {
    "Deezer genres":        "outputs/.deezer_cache.json",
    "Spotify artist genres": "outputs/.spotify_genres_cache.json",
    "Last.fm":              "outputs/.lastfm_cache.json",
    "AudioDB":              "outputs/.audiodb_cache.json",
    "Discogs":              "outputs/.discogs_cache.json",
    "Musixmatch":           "outputs/.musixmatch_cache.json",
    "Lyrics":               "outputs/.lyrics_cache.json",
    "Genius":               "outputs/.genius_cache.json",
    "Playlist mining":      "outputs/.mining_cache.json",
    "MusicBrainz":          "outputs/.mb_cache.json",
}

_cache_keys = list(cache_files.items())
_cache_rows = [_cache_keys[i:i+3] for i in range(0, len(_cache_keys), 3)]
for _row in _cache_rows:
    cols = st.columns(3)
    for i, (label, rel) in enumerate(_row):
        _cpath = os.path.join(_settings_root, rel)
        exists = os.path.exists(_cpath)
        size_kb = os.path.getsize(_cpath) // 1024 if exists else 0
        with cols[i]:
            st.metric(label, f"{size_kb} KB" if exists else "empty")

st.markdown("")
_confirm = st.checkbox(
    "I understand the next scan will re-download mining, lyrics, and API caches",
    key="cache_clear_ack",
)
if st.button(
    "Clear all caches (force full re-enrichment on next scan)",
    type="secondary",
    disabled=not _confirm,
):
    cleared = []
    for label, rel in cache_files.items():
        path = rel if os.path.isabs(rel) else os.path.join(_settings_root, rel)
        if os.path.exists(path):
            try:
                os.remove(path)
                cleared.append(label)
            except Exception:
                pass
    if cleared:
        st.success(f"Cleared: {', '.join(cleared)}")
    else:
        st.info("No caches found to clear.")
