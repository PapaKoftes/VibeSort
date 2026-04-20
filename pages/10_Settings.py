"""
pages/9_Settings.py — Vibesort Settings & Configuration.
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

def _key_status(value: str) -> str:
    if not value:
        return "not set"
    masked = value[:4] + "•" * min(len(value) - 4, 12) + value[-2:] if len(value) > 6 else "•••"
    return f"configured ({masked})"


# ── Resolve active credentials ────────────────────────────────────────────────

sp_token  = bool(st.session_state.get("spotify_token"))
lf_session = st.session_state.get("lastfm_session") or {}
lf_username = lf_session.get("name", "")
lf_key = (
    getattr(cfg, "VIBESORT_LASTFM_API_KEY", "").strip()
    or st.session_state.get("lastfm_api_key_runtime", "")
    or getattr(cfg, "LASTFM_API_KEY", "").strip()
)
lb_token = (
    st.session_state.get("listenbrainz_token_runtime")
    or getattr(cfg, "LISTENBRAINZ_TOKEN", "").strip()
)
lb_user = (
    st.session_state.get("listenbrainz_username_runtime")
    or getattr(cfg, "LISTENBRAINZ_USERNAME", "").strip()
)
genius_key      = getattr(cfg, "GENIUS_API_KEY",      "").strip()
mx_key          = getattr(cfg, "MUSIXMATCH_API_KEY",   "").strip()
discogs_tok     = getattr(cfg, "DISCOGS_TOKEN",        "").strip()
bandcamp_user   = getattr(cfg, "BANDCAMP_USERNAME",    "").strip()
beets_db        = getattr(cfg, "BEETS_DB_PATH",        "").strip()
rym_path        = getattr(cfg, "RYM_EXPORT_PATH",      "").strip()
acoustid_key    = getattr(cfg, "ACOUSTID_API_KEY",     "").strip()
local_music_dir = getattr(cfg, "LOCAL_MUSIC_PATH",     "").strip()
maloja_url      = (st.session_state.get("maloja_url_runtime") or getattr(cfg, "MALOJA_URL", "").strip())

# ── Page ──────────────────────────────────────────────────────────────────────

st.title("⚙️ Settings")

# ═════════════════════════════════════════════════════════════════════════════
# 1. Connections — most actionable, shown first
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("## Connections")

c_sp, c_lf, c_lb = st.columns(3)

with c_sp:
    with st.container(border=True):
        st.markdown("### Spotify")
        if sp_token:
            uname = st.session_state.get("me", {}).get("display_name", "Connected")
            st.success(f"✅ {uname}")
            if st.button("Disconnect", key="sp_disc", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.switch_page("pages/1_Connect.py")
        else:
            st.error("❌ Not connected")
            if st.button("Connect →", key="sp_conn", type="primary", use_container_width=True):
                st.switch_page("pages/1_Connect.py")

with c_lf:
    with st.container(border=True):
        st.markdown("### Last.fm")
        if lf_username:
            st.success(f"✅ {lf_username}")
        elif lf_key:
            st.info("🔑 API key active — not logged in")
        else:
            st.warning("⚠️ Not connected")
        if st.button("Manage →", key="lf_goto", use_container_width=True):
            st.switch_page("pages/1_Connect.py")

with c_lb:
    with st.container(border=True):
        st.markdown("### ListenBrainz")
        if lb_token and lb_user:
            st.success(f"✅ {lb_user}")
        else:
            st.info("➕ Not connected")
        if st.button("Manage →", key="lb_goto", use_container_width=True):
            st.switch_page("pages/1_Connect.py")

with st.expander("Spotify Dev Mode limitations & workarounds"):
    st.markdown(
        """
| Endpoint | Status | Workaround |
|---|---|---|
| `GET /audio-features` | ❌ Deprecated Nov 2024 | AudioDB `intBPM` (partial) |
| `GET /artists?ids=` | ❌ 403 in Dev Mode | `/v1/search` fallback ✅ |
| `GET /playlists/{id}/items` | ❌ 403 for all playlists | Last.fm / Deezer / AudioDB ✅ |

**Permanent fix:** Apply for [Extended Quota Mode](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)
to remove the 403 restrictions and unlock full playlist mining.

**Note:** Audio features (`energy`, `valence`, etc.) are permanently removed from the Spotify
API — Extended Quota Mode will **not** bring them back.
        """
    )

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# 2. Playlist generation — tunable every session
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("## Playlist generation")
st.caption("These settings apply immediately — no restart needed.")

col_l, col_r = st.columns(2)

with col_l:
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
        min_value=5, max_value=50,
        value=int(st.session_state.get("playlist_min_size", 20)), step=5,
    )
    st.session_state["playlist_min_size"] = min_playlist_size

with col_r:
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

# ═════════════════════════════════════════════════════════════════════════════
# 3. Enrichment sources — status overview
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("## Enrichment Sources")
st.caption("Signals that power mood detection, genre classification, and track scoring.")

# Row 1: always-on built-ins
r1a, r1b, r1c = st.columns(3)

with r1a:
    with st.container(border=True):
        st.markdown("**Deezer** · Genre enrichment")
        st.success("Always active")
        st.caption("Artist genres — no API key needed, cached after first scan.")
        try:
            from core.deezer import cache_stats as _dz_cache
            _dzn = _dz_cache().get("artists_cached", 0)
            if _dzn:
                st.caption(f"Cache: {_dzn} artists")
        except Exception:
            pass

with r1b:
    with st.container(border=True):
        st.markdown("**TheAudioDB** · Mood & genre labels")
        st.success("Always active")
        st.caption("Editorial mood labels per artist and track — feeds directly into scoring.")
        try:
            from core.audiodb import cache_stats as _adb_cache
            _adb = _adb_cache()
            _an = _adb.get("artists_cached", 0)
            _tn = _adb.get("tracks_cached", 0)
            if _an or _tn:
                st.caption(f"Cache: {_an} artists · {_tn} tracks")
        except Exception:
            pass

with r1c:
    with st.container(border=True):
        st.markdown("**Discogs** · Sub-genre styles")
        st.success("Always active")
        st.caption("Precise style labels (Cloud Rap, Shoegaze, Trip-Hop…) that fill gaps in Deezer.")
        _dk = discogs_tok
        if _dk:
            st.caption(f"Token: {_key_status(_dk)} — higher rate limit active")
        else:
            st.caption("No token — 25 req/min (add `DISCOGS_TOKEN` to raise to 60)")
        try:
            from core.discogs import _load_cache as _dc_load
            _dc_n = len((_dc_load()).get("artists", {}))
            if _dc_n:
                st.caption(f"Cache: {_dc_n} artists")
        except Exception:
            pass

# Row 2: lyrics
r2a, r2b = st.columns(2)

with r2a:
    with st.container(border=True):
        st.markdown("**Lyrics** · Lyrical mood analysis")
        st.success("Always active")
        st.caption(
            "Fetches lyrics from lrclib.net + lyrics.ovh and scores mood keywords "
            "(sad, dark, love, hype, party…). Cached in `.lyrics_cache.json`."
        )

with r2b:
    with st.container(border=True):
        st.markdown("**Genius** · Lyrics fallback")
        if genius_key:
            st.success(f"Active — {_key_status(genius_key)}")
        else:
            st.info("Optional — adds coverage for tracks lrclib/lyrics.ovh miss")
        st.caption("`GENIUS_API_KEY=` in `.env` · [genius.com/api-clients](https://genius.com/api-clients)")

# Row 3: optional enrichers
r3a, r3b = st.columns(2)

with r3a:
    with st.container(border=True):
        st.markdown("**Last.fm** · Artist & track mood tags")
        if lf_key:
            status_label = f"✅ Active" + (f" — logged in as {lf_username}" if lf_username else "")
            st.success(status_label)
        else:
            st.warning("⚠️ Not connected — strongly recommended")
        st.caption(
            "Crowd-sourced mood + genre tags per artist and track. "
            "Significantly improves playlist quality."
        )
        if not lf_key:
            if st.button("Connect on Connect page →", key="settings_lf_goto"):
                st.switch_page("pages/1_Connect.py")
        try:
            from core.lastfm import cache_stats as _lf_cache
            _lfs = _lf_cache()
            _la, _lt = _lfs.get("artists_cached", 0), _lfs.get("tracks_cached", 0)
            if _la or _lt:
                st.caption(f"Cache: {_la} artists · {_lt} tracks")
        except Exception:
            pass

with r3b:
    with st.container(border=True):
        st.markdown("**Musixmatch** · Per-track genre tags")
        if mx_key:
            st.success(f"Active — {_key_status(mx_key)}")
        else:
            st.info("Optional — exact per-track genre via ISRC")
        st.caption(
            "2,000 API calls/day free. Cached after first scan. "
            "`MUSIXMATCH_API_KEY=` in `.env` · "
            "[developer.musixmatch.com](https://developer.musixmatch.com/)"
        )
        try:
            from core.musixmatch import cache_stats as _mx_cache
            _mxn = _mx_cache().get("tracks_cached", 0)
            if _mxn:
                st.caption(f"Cache: {_mxn} tracks")
        except Exception:
            pass

# Row 4: Phase 2 data sources
st.markdown("#### Community & Local Sources")
r4a, r4b = st.columns(2)

with r4a:
    with st.container(border=True):
        st.markdown("**Bandcamp** · Underground taste signal")
        if bandcamp_user:
            st.success(f"Active — @{bandcamp_user}")
        else:
            st.info("Optional — your purchases/wishlist reveal underground genres")
        st.caption(
            "Set `BANDCAMP_USERNAME=` in `.env` or Connect page. "
            "Collection must be public."
        )
        if bandcamp_user:
            try:
                from core.bandcamp import _load_cache as _bc_load
                _bc_cache = _bc_load()
                if bandcamp_user.lower() in _bc_cache:
                    _n = len(_bc_cache[bandcamp_user.lower()].get("items", []))
                    st.caption(f"Cache: {_n} collection items")
            except Exception:
                pass

with r4b:
    with st.container(border=True):
        st.markdown("**beets** · Local library tags")
        try:
            from core import beets as _bm
            _beets_ok = _bm.is_available(beets_db or None)
        except Exception:
            _beets_ok = False
        if _beets_ok:
            st.success("Database found — will enrich on next scan")
            st.caption(f"Path: {beets_db or 'auto-detected'}")
        else:
            st.info("Optional — hand-curated genre/mood tags from beets library.db")
        st.caption("Set `BEETS_DB_PATH=` in `.env` or leave blank to auto-detect `~/.config/beets/library.db`")

r5a, r5b = st.columns(2)

with r5a:
    with st.container(border=True):
        st.markdown("**Rate Your Music** · Deep genre taxonomy")
        if rym_path and os.path.exists(rym_path):
            st.success(f"Export found — {os.path.basename(rym_path)}")
        elif rym_path:
            st.warning(f"File not found: {rym_path}")
        else:
            st.info("Optional — 600+ micro-genres + mood descriptors from your RYM collection")
        st.caption(
            "Export from rateyourmusic.com → Profile → Export Data. "
            "Set `RYM_EXPORT_PATH=` in `.env`."
        )

with r5b:
    with st.container(border=True):
        st.markdown("**AcoustID** · Audio fingerprinting")
        _aidm = None
        try:
            from core import acoustid as _aidm
            _fpcalc_ok = _aidm.is_available()
        except Exception:
            _fpcalc_ok = False
        if acoustid_key and _fpcalc_ok:
            st.success("API key + fpcalc ready")
            if local_music_dir:
                st.caption(f"Music dir: {local_music_dir}")
            else:
                st.caption("Set `LOCAL_MUSIC_PATH=` to fingerprint local files")
        elif acoustid_key:
            st.warning("API key set but `fpcalc` not found on PATH")
            st.caption("Install Chromaprint: acoustid.org/chromaprint")
        else:
            st.info("Optional — identify local files not in Spotify by audio fingerprint")
        st.caption(
            "Free key at acoustid.org/login. "
            "Requires Chromaprint's `fpcalc` binary."
        )
        if acoustid_key:
            try:
                _ac_stats = _aidm.cache_stats()
                if _ac_stats.get("fingerprints_cached"):
                    st.caption(f"Cache: {_ac_stats['fingerprints_cached']} fingerprints")
            except Exception:
                pass

st.markdown("#### Self-hosted Listening History")
r6a, r6b = st.columns(2)

with r6a:
    with st.container(border=True):
        st.markdown("**Maloja** · Self-hosted scrobble server")
        if maloja_url:
            st.success(f"Connected — {maloja_url}")
        else:
            st.info("Optional — self-hosted Last.fm alternative. Connect on the Connect page.")
        st.caption(
            "[maloja.krateng.ch](https://maloja.krateng.ch) — "
            "set `MALOJA_URL` + `MALOJA_TOKEN` in `.env` or Connect page."
        )

st.markdown("#### Self-hosted Music Servers")
r7a, r7b = st.columns(2)

_nd_url  = getattr(cfg, "NAVIDROME_URL",  "").strip()
_nd_user = getattr(cfg, "NAVIDROME_USER", "").strip()
_plex_url   = getattr(cfg, "PLEX_URL",   "").strip()
_plex_token = getattr(cfg, "PLEX_TOKEN", "").strip()

with r7a:
    with st.container(border=True):
        st.markdown("**Navidrome / Jellyfin** · OpenSubsonic server")
        if _nd_url and _nd_user:
            st.success(f"Connected — {_nd_url} (as {_nd_user})")
            try:
                from core import navidrome as _ndm
                _nd_cache = _ndm._session_cache.get(f"{_nd_url}:{_nd_user}", {})
                if _nd_cache.get("starred"):
                    st.caption(f"Cache: {len(_nd_cache['starred'])} starred tracks")
            except Exception:
                pass
        else:
            st.info("Optional — starred tracks & local genre tags. Connect on the Connect page.")
        st.caption(
            "[navidrome.org](https://www.navidrome.org) / [jellyfin.org](https://jellyfin.org) — "
            "set `NAVIDROME_URL`, `NAVIDROME_USER`, `NAVIDROME_PASS` in `.env` or Connect page."
        )

with r7b:
    with st.container(border=True):
        st.markdown("**Plex** · Plex Media Server")
        if _plex_url and _plex_token:
            st.success(f"Connected — {_plex_url}")
            try:
                from core import plex as _plexm
                _plex_cache = _plexm._session_cache.get(f"{_plex_url}:tracks", {})
                if _plex_cache.get("tracks"):
                    st.caption(f"Cache: {len(_plex_cache['tracks'])} tracks")
            except Exception:
                pass
        else:
            st.info("Optional — rated/played tracks & local genre tags. Connect on the Connect page.")
        st.caption(
            "[plex.tv](https://www.plex.tv) — "
            "set `PLEX_URL` + `PLEX_TOKEN` in `.env` or Connect page."
        )

_am_xml_path = getattr(cfg, "APPLE_MUSIC_XML_PATH", "").strip()
st.markdown("#### Apple Music")
r8a, _r8b = st.columns(2)
with r8a:
    with st.container(border=True):
        st.markdown("**Apple Music** · Library XML import")
        try:
            from core import apple_music as _amm
            _am_st = _amm.library_stats(_am_xml_path or None)
            if _am_st.get("available"):
                st.success(
                    f"Loaded — {_am_st['total_tracks']:,} tracks · "
                    f"{_am_st['loved']} loved · {_am_st['rated_4plus']} rated 4+"
                )
                st.caption(f"`{_am_st['xml_path']}`")
            else:
                st.info("Optional — loved/rated tracks & genre tags from your Apple Music library.")
        except Exception:
            st.info("Optional — loved/rated tracks & genre tags from your Apple Music library.")
        st.caption(
            "Export from Apple Music: File → Library → Export Library... — "
            "set `APPLE_MUSIC_XML_PATH` in `.env` or Connect page."
        )

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# 4. Quick connection tests
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("## Quick Tests")
st.caption("Probe live API connections using your current credentials.")

_tc1, _tc2, _tc3 = st.columns(3)
with _tc1:
    if st.button("Test Last.fm", use_container_width=True, key="probe_lastfm"):
        if lf_key:
            with st.spinner("Testing…"):
                try:
                    from core.lastfm import get_artist_tags
                    _tags = get_artist_tags("The Beatles", lf_key)
                    if _tags:
                        st.success(f"OK — {len(_tags)} tags for test artist")
                    else:
                        st.warning("No tags returned — check key or network")
                except Exception as _e:
                    st.error(str(_e))
        else:
            st.info("Connect Last.fm on the Connect page first")
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
            st.info("Connect ListenBrainz on the Connect page first")
with _tc3:
    if st.button("Check Genius key", use_container_width=True, key="probe_genius"):
        if genius_key and len(genius_key) > 16:
            st.success("Key format looks valid")
        elif genius_key:
            st.warning("Key seems short — verify at genius.com/api-clients")
        else:
            st.info("Add GENIUS_API_KEY in .env for extra lyrics coverage")

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# 5. Playlist defaults — server-side caps, rarely changed
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("## Playlist defaults")
st.caption("Server-side caps and scoring weights — edit `.env` and restart the app to apply.")

with st.expander("View current values and explanations"):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Current values**")
        settings = {
            "PLAYLIST_PREFIX":          getattr(cfg, "PLAYLIST_PREFIX", "Vibesort: "),
            "MAX_TRACKS_PER_PLAYLIST":  getattr(cfg, "MAX_TRACKS_PER_PLAYLIST", 75),
            "RECS_PER_PLAYLIST":        getattr(cfg, "RECS_PER_PLAYLIST", 22),
            "MIN_PLAYLIST_TOTAL":       getattr(cfg, "MIN_PLAYLIST_TOTAL", 30),
            "MIN_SONGS_PER_GENRE":      getattr(cfg, "MIN_SONGS_PER_GENRE", 5),
            "MIN_SONGS_PER_ARTIST":     getattr(cfg, "MIN_SONGS_PER_ARTIST", 8),
            "COHESION_THRESHOLD":       getattr(cfg, "COHESION_THRESHOLD", 0.55),
            "NICHE_MOODS_GENRE_GATE":   getattr(cfg, "NICHE_MOODS_GENRE_GATE", 3),
            "W_METADATA_AUDIO":         getattr(cfg, "W_METADATA_AUDIO", 0.15),
            "W_TAGS":                   getattr(cfg, "W_TAGS", 0.45),
            "W_SEMANTIC":               getattr(cfg, "W_SEMANTIC", 0.22),
            "W_GENRE":                  getattr(cfg, "W_GENRE", 0.18),
            "ALLOW_MVP_FALLBACK":       getattr(cfg, "ALLOW_MVP_FALLBACK", True),
            "MVP_MIN_PLAYLIST_SIZE":    getattr(cfg, "MVP_MIN_PLAYLIST_SIZE", 22),
            "MVP_SCORE_FLOOR":          getattr(cfg, "MVP_SCORE_FLOOR", 0.15),
        }
        for k, v in settings.items():
            st.code(f"{k}={v}", language="bash")
    with col_b:
        st.markdown("**What they do**")
        st.markdown(
            """
- `PLAYLIST_PREFIX` — prefix on all deployed playlist names
- `MAX_TRACKS_PER_PLAYLIST` — hard cap per mood/genre playlist
- `RECS_PER_PLAYLIST` — max Spotify recommendations added to pad a playlist
- `MIN_PLAYLIST_TOTAL` — minimum tracks (library + recs) a mood must reach to survive; playlists shorter than this are dropped
- `MIN_SONGS_PER_GENRE` — min tracks for a genre playlist to appear
- `MIN_SONGS_PER_ARTIST` — min tracks for an artist spotlight
- `COHESION_THRESHOLD` — baseline cohesion gate (adjusted by strictness slider)
- `NICHE_MOODS_GENRE_GATE` — min library tracks matching a mood's genres before that mood is even attempted; lower to 1–2 in Dev Mode for wider coverage
- `W_METADATA_AUDIO` / `W_TAGS` / `W_SEMANTIC` / `W_GENRE` — scoring weights (must sum to 1.0)
- `ALLOW_MVP_FALLBACK` — relax scoring when a mood has very few matches
- `MVP_MIN_PLAYLIST_SIZE` / `MVP_SCORE_FLOOR` — MVP pass trigger and floor

> **Score ceiling:** Without Spotify audio features (the default), maximum track
> score is **~0.85**. Thresholds are calibrated to this ceiling.
            """
        )

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# 6. .env template
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("## .env Template")
st.caption("Copy into your `.env` file and fill in the keys you have.")

env_template = """\
# ── Spotify (only needed if using your own app — shared PKCE app works out of the box)
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=https://papakoftes.github.io/VibeSort/callback.html

# ── Last.fm (strongly recommended — free at last.fm/api/account/create)
LASTFM_API_KEY=
LASTFM_API_SECRET=
LASTFM_USERNAME=

# ── Musixmatch (recommended — free at developer.musixmatch.com)
MUSIXMATCH_API_KEY=

# ── Genius (optional — lyrics fallback, genius.com/api-clients)
GENIUS_API_KEY=

# ── Discogs (optional — raises rate limit 25→60 req/min, discogs.com/settings/developers)
DISCOGS_TOKEN=

# ── ListenBrainz (optional — free at listenbrainz.org)
LISTENBRAINZ_TOKEN=
LISTENBRAINZ_USERNAME=

# ── Playlist settings
# PLAYLIST_PREFIX omitted — defaults to "Vibesort: " (with space) from config.py
MAX_TRACKS_PER_PLAYLIST=75
RECS_PER_PLAYLIST=22
MIN_PLAYLIST_TOTAL=30
MIN_SONGS_PER_GENRE=5
MIN_SONGS_PER_ARTIST=8
COHESION_THRESHOLD=0.55
# NICHE_MOODS_GENRE_GATE=3   # lower to 1-2 in Dev Mode for wider mood coverage
ALLOW_MVP_FALLBACK=true
MVP_MIN_PLAYLIST_SIZE=22
MVP_SCORE_FLOOR=0.15

# ── Scoring weights (must sum to 1.0)
W_METADATA_AUDIO=0.15
W_TAGS=0.45
W_SEMANTIC=0.22
W_GENRE=0.18
"""
st.code(env_template, language="bash")

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# 7. Custom Playlist Builder
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("## 🎛️ Custom Playlist Builder")
st.caption(
    "Build one specific playlist by combining a vibe, a lyrical theme, and an energy level. "
    "E.g. 'Heartbreak vibes, upbeat energy, songs about goodbye' — "
    "great for a workout after a breakup."
)

_vibe_scan = st.session_state.get("vibesort")

if not _vibe_scan:
    st.info("Run a library scan first (Scan page) — the builder uses your scored results.")
else:
    _all_tracks   = _vibe_scan.get("all_tracks", [])
    _track_tags   = _vibe_scan.get("track_tags", {})
    _profiles     = _vibe_scan.get("profiles", {})
    _mood_results = _vibe_scan.get("mood_results", {})
    _uri_to_track = {t["uri"]: t for t in _all_tracks if t.get("uri")}

    # ── Available lyric tags ──────────────────────────────────────────────────
    import collections as _col
    _all_tag_counts = _col.Counter()
    for _tv in _track_tags.values():
        for _tg in _tv:
            _all_tag_counts[_tg] += 1

    _lyr_available = sorted(
        [(t.replace("lyr_", ""), t, c) for t, c in _all_tag_counts.items() if t.startswith("lyr_")],
        key=lambda x: -x[2],
    )

    _energy_tags = ["energetic", "chill", "intense", "mellow", "dance", "calm", "aggressive", "soothing"]
    _energy_available = [(t, t.replace("_", " ").title(), _all_tag_counts.get(t, 0)) for t in _energy_tags if _all_tag_counts.get(t, 0) > 0]

    # ── Controls ──────────────────────────────────────────────────────────────
    _cb1, _cb2, _cb3 = st.columns([2, 2, 2])

    with _cb1:
        _base_mood = st.selectbox(
            "Base vibe",
            options=["(none — use whole library)"] + sorted(_mood_results.keys()),
            help="Starting point: all tracks scored for this mood. Pick '(none)' to search the full library.",
        )

    with _cb2:
        _lyr_labels  = [f"{label} ({c} tracks)" for label, tag, c in _lyr_available]
        _lyr_choices = st.multiselect(
            "Lyrical theme (any match)",
            options=[f"{label} ({c} tracks)" for label, tag, c in _lyr_available],
            help="Filter to tracks whose lyrics match at least one chosen theme.",
        )
        _chosen_lyr_tags = {
            _lyr_available[i][1]
            for i, lbl in enumerate(_lyr_labels)
            if lbl in _lyr_choices
        }

    with _cb3:
        _energy_labels  = [f"{label} ({c} tracks)" for tag, label, c in _energy_available]
        _energy_choices = st.multiselect(
            "Energy / mood tags (any match)",
            options=_energy_labels,
            help="Filter to tracks tagged with at least one energy level.",
        )
        _chosen_energy_tags = {
            _energy_available[i][0]
            for i, lbl in enumerate(_energy_labels)
            if lbl in _energy_choices
        }

    _cb4, _cb5, _cb6 = st.columns([2, 1, 1])
    with _cb4:
        _extra_tags_raw = st.text_input(
            "Extra tags to require (comma-separated)",
            placeholder="e.g. rap, dark, lyr_revenge",
            help="All listed tags must be present — AND filter. Leave blank to skip.",
        )
        _extra_tags = {t.strip().lower() for t in _extra_tags_raw.split(",") if t.strip()} if _extra_tags_raw else set()

    with _cb5:
        _playlist_size = st.slider("Playlist size", min_value=10, max_value=50, value=25, step=5)

    with _cb6:
        _artist_cap = st.slider("Max per artist", min_value=1, max_value=10, value=3, step=1,
                                help="Hard cap on how many tracks from one artist appear.")

    _playlist_name = st.text_input(
        "Playlist name",
        value=f"Custom — {_base_mood}" if _base_mood and _base_mood != "(none — use whole library)" else "My Custom Mix",
        placeholder="Give it a name",
    )

    if st.button("Build Playlist", type="primary", use_container_width=True):
        # ── Step 1: candidate pool ────────────────────────────────────────────
        if _base_mood and _base_mood != "(none — use whole library)":
            _md = _mood_results.get(_base_mood, {})
            _pool_uris = _md.get("uris", [])
            _pool_scored = {uri: sc for uri, sc in _md.get("ranked", [])}
        else:
            # Use all tracks, scored 1.0 each (no base mood signal)
            _pool_uris = [t["uri"] for t in _all_tracks if t.get("uri")]
            _pool_scored = {u: 1.0 for u in _pool_uris}

        # ── Step 2: lyrical filter (OR logic — any lyr tag matches) ──────────
        if _chosen_lyr_tags:
            _pool_uris = [
                u for u in _pool_uris
                if any(t in _track_tags.get(u, {}) for t in _chosen_lyr_tags)
            ]

        # ── Step 3: energy filter (OR logic) ─────────────────────────────────
        if _chosen_energy_tags:
            _pool_uris = [
                u for u in _pool_uris
                if any(t in _track_tags.get(u, {}) for t in _chosen_energy_tags)
            ]

        # ── Step 4: extra required tags (AND logic) ───────────────────────────
        if _extra_tags:
            _pool_uris = [
                u for u in _pool_uris
                if all(t in _track_tags.get(u, {}) for t in _extra_tags)
            ]

        # ── Step 5: sort by base mood score, then apply artist diversity cap ──
        _scored_pool = sorted(
            [(u, _pool_scored.get(u, 0.5)) for u in _pool_uris],
            key=lambda x: -x[1],
        )

        # Enforce artist diversity
        _seen_artists: dict = {}
        _diverse: list = []
        _overflow: list = []
        for u, sc in _scored_pool:
            prof = _profiles.get(u, {})
            artists = prof.get("artists") or []
            akey = str(artists[0]).lower() if artists else u
            if _seen_artists.get(akey, 0) < _artist_cap:
                _seen_artists[akey] = _seen_artists.get(akey, 0) + 1
                _diverse.append((u, sc))
            else:
                _overflow.append((u, sc))

        # Backfill from overflow if needed
        for u, sc in _overflow:
            if len(_diverse) >= _playlist_size:
                break
            prof = _profiles.get(u, {})
            artists = prof.get("artists") or []
            akey = str(artists[0]).lower() if artists else u
            if _seen_artists.get(akey, 0) < (_artist_cap + 2):
                _seen_artists[akey] = _seen_artists.get(akey, 0) + 1
                _diverse.append((u, sc))

        _final = _diverse[:_playlist_size]

        if not _final:
            st.warning(
                f"No tracks matched your filters. "
                f"{'Try removing some filters' if (_chosen_lyr_tags or _chosen_energy_tags or _extra_tags) else 'Try a different base vibe'}."
            )
        else:
            st.success(f"Built **{len(_final)} tracks** matching your criteria.")

            # Show playlist preview
            with st.expander(f"Preview — {_playlist_name}", expanded=True):
                for _i, (u, sc) in enumerate(_final, 1):
                    t = _uri_to_track.get(u, {})
                    _a = (t.get("artists") or [{}])[0].get("name", "?") if isinstance((t.get("artists") or [{}])[0], dict) else (t.get("artists") or ["?"])[0]
                    _ttitle = t.get("name", "?")
                    _ttags  = [tg for tg in list(_track_tags.get(u, {}).keys())[:6]]
                    st.markdown(
                        f"`{_i:2d}.` **{_ttitle}** — {_a}  "
                        f"<span style='color:#888;font-size:0.8em'>{', '.join(_ttags)}</span>",
                        unsafe_allow_html=True,
                    )

            # Stage or deploy buttons
            _sp = st.session_state.get("sp")
            _sc1, _sc2 = st.columns(2)
            with _sc1:
                if st.button("Stage it →", use_container_width=True, key="custom_stage"):
                    try:
                        from staging import staging as _staging_mod
                        _staging_mod.save({
                            "suggested_name": _playlist_name,
                            "track_uris":     [u for u, _ in _final],
                            "rec_uris":       [],
                            "expand_with_recs": False,
                            "cohesion":       0.0,
                            "source_type":    "custom",
                            "source_label":   "Custom Builder",
                            "playlist_type":  "custom",
                        })
                        st.success(f"Staged as **{_playlist_name}** — deploy from the Staging page.")
                    except Exception as _se:
                        st.error(f"Could not stage playlist: {_se}")
            with _sc2:
                if _sp and st.button("Deploy to Spotify now →", use_container_width=True, key="custom_deploy"):
                    try:
                        _me = st.session_state.get("me", {})
                        _uid = _me.get("id", "")
                        with st.spinner("Creating playlist on Spotify..."):
                            _new = _sp.user_playlist_create(
                                _uid, _playlist_name, public=False,
                                description=f"Custom mix by Vibesort | {len(_final)} tracks"
                            )
                            _pid = _new["id"]
                            _uris_only = [u for u, _ in _final]
                            for _chunk in range(0, len(_uris_only), 100):
                                _sp.playlist_add_items(_pid, _uris_only[_chunk:_chunk+100])
                        st.success(f"✅ **{_playlist_name}** deployed — {len(_final)} tracks added to Spotify.")
                    except Exception as _de:
                        st.error(f"Deploy failed: {_de}")

# ═════════════════════════════════════════════════════════════════════════════
# 8. Cache management
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("## Cache")
st.caption("Caches speed up re-scans by storing API responses. Clear only if you think a cache is stale.")

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# NOTE: .last_scan_snapshot.json is intentionally excluded — it is the app's
# in-memory result state, not an API cache. Clearing it loses all scan results
# until the next scan completes. It is overwritten automatically on every scan.
cache_files = {
    "Deezer genres":         "outputs/.deezer_cache.json",
    "Spotify artist genres": "outputs/.spotify_genres_cache.json",
    "Last.fm":               "outputs/.lastfm_cache.json",
    "AudioDB":               "outputs/.audiodb_cache.json",
    "Discogs":               "outputs/.discogs_cache.json",
    "Musixmatch":            "outputs/.musixmatch_cache.json",
    "Lyrics":                "outputs/.lyrics_cache.json",
    "Genius":                "outputs/.genius_cache.json",
    "Playlist mining":       "outputs/.mining_cache.json",
    "MusicBrainz":           "outputs/.mb_cache.json",
}

_cache_keys = list(cache_files.items())
# Layout: 3-per-row, last row full-width if odd remainder
_rows = [_cache_keys[i:i+3] for i in range(0, len(_cache_keys), 3)]
for _row in _rows:
    n = len(_row)
    cols = st.columns(n) if n < 3 else st.columns(3)
    for i, (label, rel) in enumerate(_row):
        _cpath = os.path.join(_root, rel)
        exists = os.path.exists(_cpath)
        import datetime as _dt
        if exists:
            _age = (_dt.datetime.now() - _dt.datetime.fromtimestamp(os.path.getmtime(_cpath))).days
            size_kb = os.path.getsize(_cpath) // 1024
            _label_val = f"{size_kb} KB · {_age}d old"
        else:
            _label_val = "empty"
        with cols[i]:
            st.metric(label, _label_val)

st.markdown("")
st.warning(
    "**Clearing all caches** requires a full re-download of all enrichment data "
    "on your next scan. For a library of 2,000+ tracks this takes **10-15 minutes**. "
    "Only clear if you suspect corrupted cache data."
)
_confirm = st.checkbox(
    "I understand — the next scan will re-download all enrichment data (~10-15 min)",
    key="cache_clear_ack",
)
if st.button(
    "Clear all caches",
    type="secondary",
    disabled=not _confirm,
):
    cleared = []
    for label, rel in cache_files.items():
        path = rel if os.path.isabs(rel) else os.path.join(_root, rel)
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
