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
    from core import ingest, enrich
    from core import genre as genre_mod
    from core import playlist_mining
    from core import profile as profile_mod
    from core import scorer, cohesion as cohesion_mod
    from core import history_parser
    from core.mood_graph import all_moods

    progress_bar = st.progress(0, text="Starting scan...")
    status_box = st.empty()

    def step(msg: str, pct: int):
        progress_bar.progress(pct, text=msg)
        status_box.info(msg)

    try:
        # Step 1: Ingest
        step("Collecting liked songs, top tracks, and followed artists...", 5)
        all_tracks, top_tracks_list, top_artists_list = ingest.collect(sp, cfg)
        step(f"Collected {len(all_tracks)} unique tracks", 18)

        # Step 2: Enrich
        step(f"Fetching audio features for {len(all_tracks)} tracks...", 22)
        artist_genres_map, audio_features_map = enrich.gather(sp, all_tracks)
        step(
            f"Fetched audio features ({len(audio_features_map)} tracks) "
            f"and genre data ({len(artist_genres_map)} artists)",
            38,
        )

        # Step 3: Playlist mining
        moods = all_moods()
        user_uris = {t["uri"] for t in all_tracks if t.get("uri")}
        step("Running playlist mining (first run ~30s, then cached)...", 42)
        mining = playlist_mining.mine(
            sp,
            user_uris,
            moods,
            playlists_per_seed=cfg.PLAYLISTS_PER_SEED,
            force_refresh=force or cfg.MINING_FORCE_REFRESH,
        )
        track_tags = mining.get("track_tags", {})
        step(f"Playlist mining complete — {len(track_tags)} tags collected", 58)

        # Step 4: Build profiles
        step("Building track profiles...", 62)
        profiles = profile_mod.build_all(
            all_tracks, artist_genres_map, audio_features_map, track_tags
        )
        step(f"Built {len(profiles)} track profiles", 68)

        # Step 5: User taste vectors
        user_mean = profile_mod.user_audio_mean(profiles)

        # Step 6: Genre/era/artist breakdowns
        step("Analyzing genre, era, and artist patterns...", 70)
        genre_map  = genre_mod.library_genre_breakdown(all_tracks, artist_genres_map)
        era_map    = genre_mod.era_breakdown(all_tracks)
        artist_map = genre_mod.artist_breakdown(all_tracks, cfg.MIN_SONGS_PER_ARTIST)

        # Step 7: Score moods
        step(f"Scoring {len(moods)} moods against your library...", 75)
        mood_results: dict = {}
        for mood_name in moods:
            ranked = scorer.rank_tracks(
                profiles,
                mood_name,
                user_mean,
                min_score=0.22,
                weights=(cfg.W_AUDIO, cfg.W_TAGS, cfg.W_GENRE),
            )
            if not ranked:
                continue
            filtered, c_score = cohesion_mod.top_n_by_score(
                ranked,
                profiles,
                n=cfg.MAX_TRACKS_PER_PLAYLIST,
                cohesion_threshold=cfg.COHESION_THRESHOLD,
                min_tracks=5,
            )
            if len(filtered) >= 5:
                mood_results[mood_name] = {
                    "uris":     filtered,
                    "cohesion": c_score,
                    "count":    len(filtered),
                }
        step(f"Found {len(mood_results)} vibes in your library", 90)

        # Step 8: History (if available)
        history_entries = history_parser.load("data")
        history_stats   = history_parser.stats(history_entries) if history_entries else {}
        history_uris    = history_parser.sorted_uris(history_entries) if history_entries else []

        step("Scan complete.", 100)
        status_box.success(
            f"Scan complete — {len(all_tracks)} songs · "
            f"{len(genre_map)} genres · "
            f"{len(mood_results)} moods · "
            f"{len(artist_map)} artists"
        )

        return {
            "sp":               sp,
            "user_id":          user_id,
            "all_tracks":       all_tracks,
            "top_tracks":       top_tracks_list,
            "top_artists":      top_artists_list,
            "profiles":         profiles,
            "user_mean":        user_mean,
            "artist_genres":    artist_genres_map,
            "audio_features":   audio_features_map,
            "track_tags":       track_tags,
            "genre_map":        genre_map,
            "era_map":          era_map,
            "artist_map":       artist_map,
            "mood_results":     mood_results,
            "history_stats":    history_stats,
            "history_uris":     history_uris,
            "existing_uris":    user_uris,
        }

    except Exception as e:
        progress_bar.empty()
        status_box.error(f"Scan failed: {e}")
        st.exception(e)
        return None


# ── Page ─────────────────────────────────────────────────────────────────────

sp = st.session_state.get("sp")
me = st.session_state.get("me", {})
user_id = me.get("id", "")
name = me.get("display_name") or user_id

st.title("Library Scan")
st.caption(f"Scanning library for **{name}**")

vibesort = st.session_state.get("vibesort")

col_rescan, col_goto = st.columns([2, 5])
with col_rescan:
    force_rescan = st.button("Re-scan Library", use_container_width=True)

if force_rescan or not vibesort:
    with st.spinner(""):
        result = run_scan(sp, user_id, force=force_rescan)
        if result:
            st.session_state["vibesort"] = result
            vibesort = result

if vibesort:
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Songs", len(vibesort.get("all_tracks", [])))
    col2.metric("Genres", len(vibesort.get("genre_map", {})))
    col3.metric("Moods", len(vibesort.get("mood_results", {})))
    col4.metric("Artists", len(vibesort.get("artist_map", {})))

    st.write("")
    if st.button("Go to Vibes", type="primary", use_container_width=True):
        st.switch_page("pages/3_Vibes.py")
else:
    if not force_rescan:
        st.info("Click 'Re-scan Library' to analyze your Spotify library.")
