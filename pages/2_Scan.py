"""
pages/2_Scan.py — Library scan page (M1.8 redesign).

Three scan modes:
  Full Scan      — re-scores from cache, re-mines if >30 days old
  Custom Scan    — selective cache clearing per enrichment source
  Local Library  — AcoustID fingerprinting for local audio files (M1.6)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort — Scan",
    page_icon="🎧",
    layout="wide",
)
from core.theme import inject
inject()

# Guard: require auth
if not st.session_state.get("spotify_token"):
    st.warning("Please connect to Spotify first.")
    if st.button("Go to Connect"):
        st.switch_page("pages/1_Connect.py")
    st.stop()


# ── Cache paths ───────────────────────────────────────────────────────────────

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUTS = os.path.join(_ROOT, "outputs")

_CACHE_FILES = {
    "mining":        ".mining_cache.json",
    "lastfm":        ".lastfm_cache.json",
    "deezer":        ".deezer_cache.json",
    "audiodb":       ".audiodb_cache.json",
    "musicbrainz":   ".mb_cache.json",
    "lyrics":        ".lyrics_cache.json",
    "discogs":       ".discogs_cache.json",
    "acoustid":      ".acoustid_cache.json",
    "spotify_genres":".spotify_genres_cache.json",
    "snapshot":      ".last_scan_snapshot.json",
}


def _cache_path(key: str) -> str:
    return os.path.join(_OUTPUTS, _CACHE_FILES[key])


def _cache_exists(key: str) -> bool:
    return os.path.exists(_cache_path(key))


def _cache_age_str(key: str) -> str:
    """Human-readable age of a cache file."""
    p = _cache_path(key)
    if not os.path.exists(p):
        return "not cached"
    import datetime
    mtime = os.path.getmtime(p)
    age = datetime.datetime.now() - datetime.datetime.fromtimestamp(mtime)
    d, h, m = age.days, age.seconds // 3600, (age.seconds % 3600) // 60
    if d > 0:
        return f"{d}d old"
    if h > 0:
        return f"{h}h old"
    return f"{m}m old"


def _delete_cache(key: str) -> None:
    p = _cache_path(key)
    try:
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass


def _clear_lastfm_enrichment() -> None:
    """Clear only the artist/track entries from lastfm cache (keep tag_charts)."""
    import json
    p = _cache_path("lastfm")
    if not os.path.exists(p):
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            d["artists"] = {}
            d["tracks"]  = {}
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
    except Exception:
        _delete_cache("lastfm")


def _clear_deezer_tracks() -> None:
    """Clear only per-track entries from deezer cache (keep artist genres)."""
    import json
    p = _cache_path("deezer")
    if not os.path.exists(p):
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            d["tracks"] = {}
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
    except Exception:
        _delete_cache("deezer")


# ── Scan runner ───────────────────────────────────────────────────────────────

def run_scan(sp, user_id: str, force: bool = False, local_path: str = ""):
    """Run the full library scan and store results in st.session_state['vibesort']."""
    import config as cfg
    from core.scan_pipeline import execute_library_scan

    if st.session_state.get("scan_running"):
        st.warning("A scan is already running — please wait for it to finish.")
        return None

    st.session_state["scan_running"] = True

    progress_bar = st.progress(0, text="Starting scan...")
    status_box   = st.empty()

    def step(msg: str, pct: int):
        progress_bar.progress(pct, text=msg)
        status_box.markdown(
            f"<div style='"
            f"background:#0e000e;"
            f"border-left:3px solid #3d0050;"
            f"padding:10px 16px;"
            f"border-radius:4px;"
            f"font-family:JetBrains Mono,monospace;"
            f"font-size:0.85rem;"
            f"color:#b89cc8;"
            f"letter-spacing:0.03em;"
            f"'>"
            f"<span style='color:#6a2080'>›</span> {msg}"
            f"</div>",
            unsafe_allow_html=True,
        )

    def _refresh_token():
        from core.pkce import make_spotify as _pkce_sp, save_token as _pkce_save
        _token = st.session_state.get("spotify_token", {})
        _shared_id = (cfg.VIBESORT_CLIENT_ID or "").strip()
        if _shared_id and isinstance(_token, dict) and "access_token" in _token:
            sp_new, _refreshed = _pkce_sp(_token, _shared_id)
            if _refreshed is not _token:
                st.session_state["spotify_token"] = _refreshed
                st.session_state["sp"] = sp_new
                _pkce_save(_refreshed)
            return st.session_state.get("sp")
        return None

    try:
        _min_score_override = st.session_state.get("playlist_min_score", None)
        _strictness = int(st.session_state.get("strictness", 3))
        _pl_min     = int(st.session_state.get("playlist_min_size", 20))
        _pl_exp     = bool(st.session_state.get("playlist_expansion", True))
        _allow_mvp  = bool(st.session_state.get("allow_mvp_fallback", cfg.ALLOW_MVP_FALLBACK))

        # If local_path is set, inject it so the pipeline can use it
        if local_path and os.path.isdir(local_path):
            os.environ["LOCAL_MUSIC_PATH"] = local_path

        result, lyrics_lang = execute_library_scan(
            sp,
            user_id,
            cfg,
            step,
            force_refresh=force,
            refresh_spotify_token=_refresh_token,
            min_score_override=_min_score_override,
            strictness=_strictness,
            playlist_min_size=_pl_min,
            playlist_expansion=_pl_exp,
            allow_mvp_fallback=_allow_mvp,
            mvp_min_playlist_size=cfg.MVP_MIN_PLAYLIST_SIZE,
            mvp_score_floor=cfg.MVP_SCORE_FLOOR,
            corpus_mode=st.session_state.get("scan_corpus_mode", "full_library"),
            lyric_weight=float(st.session_state.get("scan_lyric_weight", 1.16)),
            max_tracks_cap=int(st.session_state.get("scan_max_tracks", 50)),
        )
        if lyrics_lang:
            st.session_state["lyrics_lang_map"] = lyrics_lang

        status_box.success(
            f"Scan complete — {len(result.get('all_tracks', []))} songs · "
            f"{len(result.get('genre_map', {}))} genres · "
            f"{len(result.get('mood_results', {}))} moods · "
            f"{len(result.get('artist_map', {}))} artists"
        )
        return result

    except Exception as e:
        progress_bar.empty()
        status_box.error(f"Scan failed: {e}")
        st.exception(e)
        return None
    finally:
        try:
            delattr(cfg, "SCAN_LYRIC_WEIGHT")
        except AttributeError:
            pass
        st.session_state.pop("scan_running", None)


# ── Page ─────────────────────────────────────────────────────────────────────

sp      = st.session_state.get("sp")
me      = st.session_state.get("me", {})
user_id = me.get("id", "")
name    = me.get("display_name") or user_id

st.title("Library Scan")
st.caption(f"Scanning library for **{name}**")

vibesort = st.session_state.get("vibesort")

# ── Last scan summary ─────────────────────────────────────────────────────────
_snapshot_age = _cache_age_str("snapshot") if _cache_exists("snapshot") else None
if vibesort and _snapshot_age:
    _n_trk  = len(vibesort.get("all_tracks", []))
    _n_mood = len(vibesort.get("mood_results", {}))
    st.caption(
        f"Last scan: **{_snapshot_age}** · {_n_trk:,} tracks · {_n_mood} moods"
    )

st.write("")

# ── Three scan mode buttons ───────────────────────────────────────────────────
col_full, col_custom, col_local = st.columns(3)

with col_full:
    st.markdown("**Full Scan**")
    st.caption(
        "Re-scores your library using all cached enrichment data. "
        "Re-fetches mood playlists if older than 30 days."
    )
    _do_full = st.button(
        "Run Full Scan",
        use_container_width=True,
        type="primary",
        key="btn_full_scan",
    )

with col_custom:
    st.markdown("**Custom Scan**")
    st.caption("Choose which data sources to refresh before re-scoring.")
    _do_custom = st.button(
        "Run Custom Scan",
        use_container_width=True,
        key="btn_custom_scan",
    )

with col_local:
    st.markdown("**Local Library Scan**")
    st.caption("Fingerprint local audio files via AcoustID and merge with Spotify library.")
    _do_local = st.button(
        "Run Local Scan",
        use_container_width=True,
        key="btn_local_scan",
    )

# ── Custom Scan settings expander ─────────────────────────────────────────────
with st.expander("Custom Scan options", expanded=_do_custom):
    st.markdown("**Re-fetch sources** — clear a cache to force fresh data on next scan.")
    _col1, _col2 = st.columns(2)

    with _col1:
        _clr_mining  = st.checkbox(
            "Re-mine mood playlists",
            help=f"Clears .mining_cache.json ({_cache_age_str('mining')}). "
                 "Re-fetches Last.fm tag charts + owned playlists. "
                 "First run: ~55s. Recommended if moods feel stale.",
        )
        _clr_lastfm  = st.checkbox(
            "Re-fetch Last.fm tags",
            help=f"Clears artist + track entries in lastfm_cache ({_cache_age_str('lastfm')}). "
                 "Keeps tag chart data. Re-enriches artist/track tags from Last.fm.",
        )
        _clr_deezer  = st.checkbox(
            "Re-fetch Deezer track data",
            help=f"Clears per-track Deezer entries ({_cache_age_str('deezer')}). "
                 "Keeps artist genre cache. Re-fetches BPM, explicit, rank.",
        )
        _clr_lyrics  = st.checkbox(
            "Re-fetch lyrics",
            help=f"Clears .lyrics_cache.json ({_cache_age_str('lyrics')}). "
                 "WARNING: slow on first run (~2-10 min for a large library).",
        )

    with _col2:
        _clr_audiodb = st.checkbox(
            "Re-fetch AudioDB",
            help=f"Clears .audiodb_cache.json ({_cache_age_str('audiodb')}). "
                 "Re-fetches artist mood/genre tags from TheAudioDB.",
        )
        _clr_mb      = st.checkbox(
            "Re-fetch MusicBrainz tags",
            help=f"Clears .mb_cache.json ({_cache_age_str('musicbrainz')}). "
                 "Re-fetches recording-level genre/mood tags.",
        )
        _clr_discogs = st.checkbox(
            "Re-fetch Discogs styles",
            help=f"Clears .discogs_cache.json ({_cache_age_str('discogs')}). "
                 "Re-fetches sub-genre style labels (Cloud Rap, Shoegaze, etc.).",
        )
        _score_only  = st.checkbox(
            "Re-run scoring only (fastest)",
            help="Keeps all caches. Only re-runs mood scoring from cached enrichment data. "
                 "Use when you change packs.json or scoring settings.",
        )

# ── Local Library path input ─────────────────────────────────────────────────
with st.expander("Local Library Scan options", expanded=_do_local):
    _local_path = st.text_input(
        "Music root directory",
        placeholder=r"C:\Music   or   /home/user/Music",
        help="Path to your local music folder. Vibesort will scan recursively for "
             "audio files (.mp3, .flac, .aac, .ogg, .m4a, .wav) and fingerprint them "
             "via AcoustID to enrich mood tags.",
        value=st.session_state.get("local_music_path", ""),
    )
    if _local_path:
        st.session_state["local_music_path"] = _local_path
        if os.path.isdir(_local_path):
            _audio_exts = {".mp3", ".flac", ".aac", ".ogg", ".m4a", ".wav"}
            try:
                _audio_files = [
                    f for _, _, files in os.walk(_local_path)
                    for f in files
                    if os.path.splitext(f)[1].lower() in _audio_exts
                ]
                st.info(
                    f"Found **{len(_audio_files)} audio files** in that directory. "
                    f"Estimated fingerprinting: ~{max(1, len(_audio_files) // 60)} min "
                    f"(fpcalc processes ~60 files/min)."
                )
            except Exception:
                st.info("Directory found — file count unavailable.")
        elif _local_path:
            st.warning("Directory not found — check the path and try again.")

    import shutil
    _fpcalc_found = bool(shutil.which("fpcalc"))
    if not _fpcalc_found:
        st.warning(
            "fpcalc not found on PATH. Install Chromaprint to enable fingerprinting: "
            "https://acoustid.org/chromaprint"
        )

# ── General scan options expander ─────────────────────────────────────────────
with st.expander("Scoring options", expanded=False):
    _mode_labels = {
        "full_library": "Full library (liked + tops + followed + playlists)",
        "liked_only":   "Liked songs only",
    }
    _selected_label = st.radio(
        "Scan corpus",
        options=list(_mode_labels.values()),
        index=0 if st.session_state.get("scan_corpus_mode", "full_library") == "full_library" else 1,
    )
    _selected_mode = next(k for k, v in _mode_labels.items() if v == _selected_label)
    st.session_state["scan_corpus_mode"] = _selected_mode

    st.session_state["strictness"] = st.slider(
        "Strictness (higher = tighter playlists)",
        min_value=1, max_value=5,
        value=int(st.session_state.get("strictness", 3)),
        help="Raises cohesion threshold and drop ratio when increased.",
    )
    st.session_state["playlist_min_size"] = st.slider(
        "Minimum tracks we try to keep per mood",
        min_value=15, max_value=60,
        value=int(st.session_state.get("playlist_min_size", 25)),
    )
    st.session_state["scan_max_tracks"] = st.slider(
        "Max tracks per mood (library picks)",
        min_value=25, max_value=80,
        value=int(st.session_state.get("scan_max_tracks", 50)),
    )
    st.session_state["scan_lyric_weight"] = st.slider(
        "Lyric emphasis for lyric-focused moods",
        min_value=1.0, max_value=1.45,
        value=float(st.session_state.get("scan_lyric_weight", 1.16)),
        step=0.02,
        help="Boosts tag scores when lyrics-derived lyr_* tags match.",
    )
    st.session_state["playlist_expansion"] = st.checkbox(
        "Backfill moods toward minimum size",
        value=st.session_state.get("playlist_expansion", True),
    )
    st.session_state["allow_mvp_fallback"] = st.checkbox(
        "Allow relaxed pass if a mood is thin",
        value=st.session_state.get("allow_mvp_fallback", True),
    )

# ── Trigger logic ─────────────────────────────────────────────────────────────
auto_scan     = not vibesort and not st.session_state.get("scan_failed")
_trigger_full  = _do_full or auto_scan
_trigger_custom = _do_custom
_trigger_local  = _do_local and _local_path and os.path.isdir(_local_path)

result = None

if _trigger_custom:
    # Apply selective cache clearing before scan
    if _clr_mining:  _delete_cache("mining")
    if _clr_lastfm:  _clear_lastfm_enrichment()
    if _clr_deezer:  _clear_deezer_tracks()
    if _clr_lyrics:  _delete_cache("lyrics")
    if _clr_audiodb: _delete_cache("audiodb")
    if _clr_mb:      _delete_cache("musicbrainz")
    if _clr_discogs: _delete_cache("discogs")
    if _score_only:  _delete_cache("snapshot")   # only clear snapshot

    # force=True so mining is re-evaluated even if within 30-day TTL
    result = run_scan(sp, user_id, force=not _score_only)

elif _trigger_local:
    result = run_scan(sp, user_id, force=False, local_path=_local_path)

elif _trigger_full:
    # Full Scan: never force — lets mining cache TTL decide whether to re-mine
    result = run_scan(sp, user_id, force=False)

if result:
    st.session_state.pop("taste_fingerprint", None)
    st.session_state["vibesort"] = result
    st.session_state.pop("scan_failed", None)
    vibesort = result
elif (_trigger_full or _trigger_custom or _trigger_local) and result is None:
    st.session_state["scan_failed"] = True

# ── Post-scan summary ─────────────────────────────────────────────────────────
if vibesort:
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Songs",   len(vibesort.get("all_tracks", [])))
    col2.metric("Genres",  len(vibesort.get("genre_map", {})))
    col3.metric("Moods",   len(vibesort.get("mood_results", {})))
    col4.metric("Artists", len(vibesort.get("artist_map", {})))

    import config as _cfg_info
    _has_lf_key = bool(
        getattr(_cfg_info, "VIBESORT_LASTFM_API_KEY", "").strip()
        or getattr(_cfg_info, "LASTFM_API_KEY", "").strip()
        or st.session_state.get("lastfm_api_key_runtime", "")
    )

    _n_genres   = len(vibesort.get("genre_map", {}))
    _mining_blk = vibesort.get("mining_blocked") or vibesort.get("playlist_items_blocked")
    _zero_signal = _n_genres == 0 and _mining_blk and not _has_lf_key

    if _zero_signal:
        st.error(
            "**Zero signal — moods will be empty or random.**\n\n"
            "All three data sources are blocked in Spotify's Development Mode:\n"
            "- Playlist mining: **blocked** (403 on all playlist_items)\n"
            "- Deezer genres: **0** artists enriched\n"
            "- Audio features: **deprecated** (unavailable)\n\n"
            "**Fix this in 30 seconds:** Add a free Last.fm API key to your `.env`:\n"
            "```\nLASTFM_API_KEY=your_key_here\n```\n"
            "[Get a free key here](https://www.last.fm/api/account/create) — "
            "then click **Run Full Scan**."
        )
    elif _mining_blk:
        if _has_lf_key:
            st.info(
                "Playlist mining is blocked in Spotify's Development Mode — "
                "mood detection is powered by **Last.fm** genre + mood tags. "
                "Results should be solid. For full Spotify functionality, apply for "
                "[Extended Quota Mode](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)."
            )
        else:
            st.warning(
                "Playlist mining is blocked in Spotify's Development Mode. "
                "Genre detection via Deezer is the only active signal — results may be thin. "
                "For rich mood detection, connect your **Last.fm** account on the "
                "[Connect page](1_Connect) and re-scan."
            )

    st.write("")
    if st.button("Go to Vibes", type="primary", use_container_width=True):
        st.switch_page("pages/3_Vibes.py")

elif st.session_state.get("scan_failed"):
    st.warning("Scan failed. Fix the error above and try again.")
