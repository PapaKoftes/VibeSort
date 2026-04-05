"""
pages/2_Scan.py — Library scan page.
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


def run_scan(sp, user_id: str, force: bool = False):
    """Run the full library scan and store results in st.session_state['vibesort']."""
    import config as cfg
    from core.scan_pipeline import execute_library_scan

    if st.session_state.get("scan_running"):
        st.warning("⏳ A scan is already running — please wait for it to finish.")
        return None

    st.session_state["scan_running"] = True

    progress_bar = st.progress(0, text="Starting scan...")
    status_box = st.empty()

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

    try:  # noqa: SIM105  (finally needed for scan_running cleanup)
        _min_score_override = st.session_state.get("playlist_min_score", None)
        _strictness = int(st.session_state.get("strictness", 3))
        _pl_min = int(st.session_state.get("playlist_min_size", 20))
        _pl_exp = bool(st.session_state.get("playlist_expansion", True))
        _allow_mvp = bool(st.session_state.get("allow_mvp_fallback", cfg.ALLOW_MVP_FALLBACK))

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

sp = st.session_state.get("sp")
me = st.session_state.get("me", {})
user_id = me.get("id", "")
name = me.get("display_name") or user_id

st.title("Library Scan")
st.caption(f"Scanning library for **{name}**")

vibesort = st.session_state.get("vibesort")
_mode_labels = {
    "full_library": "Full library (liked + tops + followed + playlists)",
    "liked_only": "Liked songs only",
}
_selected_label = st.radio(
    "Scan corpus",
    options=list(_mode_labels.values()),
    index=0 if st.session_state.get("scan_corpus_mode", "full_library") == "full_library" else 1,
)
_selected_mode = next(k for k, v in _mode_labels.items() if v == _selected_label)
st.session_state["scan_corpus_mode"] = _selected_mode

with st.expander("Scan options — strictness, sizes, lyric weight", expanded=False):
    st.session_state["strictness"] = st.slider(
        "Strictness (higher = tighter playlists)",
        min_value=1,
        max_value=5,
        value=int(st.session_state.get("strictness", 3)),
        help="Raises cohesion threshold and drop ratio when increased.",
    )
    st.session_state["playlist_min_size"] = st.slider(
        "Minimum tracks we try to keep per mood",
        min_value=15,
        max_value=60,
        value=int(st.session_state.get("playlist_min_size", 25)),
    )
    st.session_state["scan_max_tracks"] = st.slider(
        "Max tracks per mood (library picks)",
        min_value=25,
        max_value=80,
        value=int(st.session_state.get("scan_max_tracks", 50)),
    )
    st.session_state["scan_lyric_weight"] = st.slider(
        "Lyric emphasis for lyric-focused moods",
        min_value=1.0,
        max_value=1.45,
        value=float(st.session_state.get("scan_lyric_weight", 1.16)),
        step=0.02,
        help="Boosts tag scores when lyrics-derived lyr_* tags match (Hollow, theme packs, etc.).",
    )
    st.session_state["playlist_expansion"] = st.checkbox(
        "Backfill moods toward minimum size",
        value=st.session_state.get("playlist_expansion", True),
    )
    st.session_state["allow_mvp_fallback"] = st.checkbox(
        "Allow relaxed pass if a mood is thin",
        value=st.session_state.get("allow_mvp_fallback", True),
    )

col_rescan, col_goto = st.columns([2, 5])
with col_rescan:
    force_rescan = st.button("Re-scan Library", use_container_width=True)

# Auto-start scan on first visit (no vibesort yet), or when user hits Re-scan
auto_scan = not vibesort and not st.session_state.get("scan_failed")

if force_rescan or auto_scan:
    result = run_scan(sp, user_id, force=force_rescan)
    if result:
        st.session_state.pop("taste_fingerprint", None)
        st.session_state["vibesort"] = result
        st.session_state.pop("scan_failed", None)
        vibesort = result
    else:
        st.session_state["scan_failed"] = True

if vibesort:
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Songs", len(vibesort.get("all_tracks", [])))
    col2.metric("Genres", len(vibesort.get("genre_map", {})))
    col3.metric("Moods", len(vibesort.get("mood_results", {})))
    col4.metric("Artists", len(vibesort.get("artist_map", {})))

    import config as _cfg_info
    _has_lf_key = bool(getattr(_cfg_info, "LASTFM_API_KEY", "").strip())

    _n_genres    = len(vibesort.get("genre_map", {}))
    _mining_blk  = vibesort.get("mining_blocked") or vibesort.get("playlist_items_blocked")
    _scan_flags  = vibesort.get("scan_flags", {})
    _zero_signal = _n_genres == 0 and _mining_blk and not _has_lf_key

    if _zero_signal:
        st.error(
            "**⚠️ Zero signal — moods will be empty or random.**\n\n"
            "All three data sources are blocked in Spotify's Development Mode:\n"
            "- Playlist mining: **blocked** (403 on all playlist_items)\n"
            "- Deezer genres: **0** artists enriched\n"
            "- Audio features: **deprecated** (unavailable)\n\n"
            "**Fix this in 30 seconds:** Add a free Last.fm API key to your `.env`:\n"
            "```\nLASTFM_API_KEY=your_key_here\n```\n"
            "[Get a free key here](https://www.last.fm/api/account/create) → "
            "Create account → Create API application → copy the API key. "
            "Then click **Re-scan Library**."
        )
    elif _mining_blk:
        if _has_lf_key:
            st.info(
                "ℹ️ **Playlist mining is blocked in Spotify's Development Mode** — "
                "mood detection is powered by **Last.fm** genre + mood tags. "
                "Results should be solid. For full Spotify functionality, apply for "
                "[Extended Quota Mode](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)."
            )
        else:
            st.warning(
                "⚠️ **Playlist mining is blocked in Spotify's Development Mode.** "
                "Genre detection via Deezer is the only active signal — results may be thin. "
                "For rich mood detection, add a free Last.fm key: "
                "`LASTFM_API_KEY=<key>` in your `.env` "
                "([get one here](https://www.last.fm/api/account/create)) and re-scan."
            )

    st.write("")
    if st.button("Go to Vibes", type="primary", use_container_width=True):
        st.switch_page("pages/3_Vibes.py")
elif st.session_state.get("scan_failed"):
    st.warning("Scan failed. Fix the error above and click Re-scan Library.")
