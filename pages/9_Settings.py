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
            "MAX_TRACKS_PER_PLAYLIST":  getattr(cfg, "MAX_TRACKS_PER_PLAYLIST", 50),
            "MIN_SONGS_PER_GENRE":      getattr(cfg, "MIN_SONGS_PER_GENRE", 5),
            "MIN_SONGS_PER_ARTIST":     getattr(cfg, "MIN_SONGS_PER_ARTIST", 8),
            "COHESION_THRESHOLD":       getattr(cfg, "COHESION_THRESHOLD", 0.60),
            "W_METADATA_AUDIO":         getattr(cfg, "W_METADATA_AUDIO", 0.10),
            "W_TAGS":                   getattr(cfg, "W_TAGS", 0.46),
            "W_SEMANTIC":               getattr(cfg, "W_SEMANTIC", 0.26),
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
- `MIN_SONGS_PER_GENRE` — min tracks for a genre playlist to appear
- `MIN_SONGS_PER_ARTIST` — min tracks for an artist spotlight
- `COHESION_THRESHOLD` — baseline for audio outlier trimming
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
PLAYLIST_PREFIX=Vibesort:
MAX_TRACKS_PER_PLAYLIST=50
MIN_SONGS_PER_GENRE=5
MIN_SONGS_PER_ARTIST=8
COHESION_THRESHOLD=0.60
ALLOW_MVP_FALLBACK=true
MVP_MIN_PLAYLIST_SIZE=22
MVP_SCORE_FLOOR=0.15
"""
st.code(env_template, language="bash")

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# 7. Cache management
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("## Cache")
st.caption("Caches avoid re-downloading data on every scan. Clear only if you think a cache is stale.")

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        size_kb = os.path.getsize(_cpath) // 1024 if exists else 0
        with cols[i]:
            st.metric(label, f"{size_kb} KB" if exists else "empty")

st.markdown("")
_confirm = st.checkbox(
    "I understand the next scan will re-download all enrichment data",
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
