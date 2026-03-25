"""
pages/4_Genres.py — Genre playlists page.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort — Genres",
    page_icon="🎧",
    layout="wide",
)

if not st.session_state.get("spotify_token"):
    st.warning("Please connect to Spotify first.")
    if st.button("Connect"):
        st.switch_page("pages/1_Connect.py")
    st.stop()

if not st.session_state.get("vibesort"):
    st.info("Scan your library first.")
    if st.button("Scan Library"):
        st.switch_page("pages/2_Scan.py")
    st.stop()

vibesort = st.session_state["vibesort"]
profiles: dict = vibesort.get("profiles", {})
genre_map: dict = vibesort.get("genre_map", {})
era_map: dict = vibesort.get("era_map", {})
all_tracks: list = vibesort.get("all_tracks", [])

try:
    import config as cfg
    MIN_GENRE = cfg.MIN_SONGS_PER_GENRE
    MIN_ERA   = cfg.MIN_SONGS_PER_ERA
except Exception:
    MIN_GENRE = 5
    MIN_ERA   = 5


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Genres")
    valid_genres = {g: uris for g, uris in genre_map.items() if len(uris) >= MIN_GENRE}
    st.metric("Genre playlists available", len(valid_genres))
    st.metric("Era playlists available", sum(1 for uris in era_map.values() if len(uris) >= MIN_ERA))

    st.divider()
    if st.button("Go to Staging Shelf", use_container_width=True):
        st.switch_page("pages/7_Staging.py")


# ── Helpers ───────────────────────────────────────────────────────────────────

GENRE_FAMILIES = {
    "All":        None,
    "Rap / Hip-Hop": ["East Coast Rap", "West Coast Rap", "Southern Rap", "Houston Rap",
                      "Midwest Rap", "UK Rap / Grime", "French Rap", "Phonk",
                      "Brazilian Phonk", "Hip-Hop / Rap"],
    "Electronic": ["Electronic / House", "Electronic / Techno", "Electronic / Drum & Bass",
                   "Electronic / Bass & Dubstep", "Electronic / Trance", "Electronic / Ambient",
                   "Synthwave / Retrowave", "Lo-Fi"],
    "Latin / Global": ["Latin / Reggaeton", "Mexican Regional", "Brazilian / Funk Carioca",
                       "Afrobeats / Amapiano", "Caribbean / Reggae", "World / Regional"],
    "R&B / Soul": ["R&B / Soul", "Dark R&B"],
    "Rock / Metal": ["Rock", "Classic Rock", "Metal", "Punk / Hardcore",
                     "Emo / Post-Hardcore", "Post-Punk / Darkwave", "Shoegaze / Dream Pop"],
    "Indie / Pop": ["Indie / Alternative", "Pop", "Hyperpop", "K-Pop / J-Pop"],
    "Folk / Jazz": ["Folk / Americana", "Jazz / Blues", "Classical / Orchestral", "Country"],
    "Ambient": ["Ambient / Experimental", "Ambient"],
}


def _genre_breakdown_for_uris(uris):
    counts = {}
    for u in uris:
        p = profiles.get(u, {})
        for macro in p.get("macro_genres", ["Other"]):
            counts[macro] = counts.get(macro, 0) + 1
    return counts


def _cohesion_for_uris(uris):
    try:
        import numpy as np
        vectors = [
            profiles[u]["audio_vector"]
            for u in uris
            if u in profiles and profiles[u].get("audio_vector")
        ]
        if len(vectors) < 2:
            return 1.0
        arr = np.array(vectors)
        mean = arr.mean(axis=0)
        dists = np.linalg.norm(arr - mean, axis=1)
        return round(float(max(0.0, 1.0 - dists.mean())), 3)
    except Exception:
        return 0.7


def _add_to_staging(genre_name, uris, playlist_type="genre"):
    try:
        from staging import staging
        from core.namer import bottom_up_name

        track_profiles_list = [profiles[u] for u in uris if u in profiles]
        name, desc = bottom_up_name(track_profiles_list)
        if genre_name and genre_name != name:
            name = genre_name
            desc = f"{genre_name} · {len(uris)} tracks"

        genre_bd = _genre_breakdown_for_uris(uris)
        total = sum(genre_bd.values()) or 1
        genre_bd_pct = {g: round(c / total, 3) for g, c in genre_bd.items()}
        cohesion = _cohesion_for_uris(uris)

        data = {
            "suggested_name":  name,
            "user_name":       name,
            "description":     desc,
            "track_uris":      list(uris),
            "rec_uris":        [],
            "playlist_type":   playlist_type,
            "source_type":     playlist_type,
            "source_label":    genre_name,
            "genre_breakdown": genre_bd_pct,
            "cohesion":        cohesion,
            "expand_with_recs": True,
        }
        pid = staging.save(data)
        if "staged_ids" not in st.session_state:
            st.session_state["staged_ids"] = []
        if pid not in st.session_state["staged_ids"]:
            st.session_state["staged_ids"].append(pid)
        return pid
    except Exception as e:
        st.error(f"Could not save: {e}")
        return None


# ── Main page ─────────────────────────────────────────────────────────────────

st.title("Genre Playlists")

tab_genres, tab_eras, tab_languages = st.tabs(["Genres", "Eras / Decades", "Languages"])

# ── TAB: Genres ───────────────────────────────────────────────────────────────
with tab_genres:
    if not valid_genres:
        st.info(f"Not enough tracks per genre (minimum {MIN_GENRE} songs required).")
    else:
        col_filter, col_addall = st.columns([3, 2])
        with col_filter:
            family_filter = st.selectbox("Filter by family", list(GENRE_FAMILIES.keys()), index=0)
        with col_addall:
            st.write("")
            if st.button("Add All to Staging", use_container_width=True):
                added = 0
                for genre, uris in valid_genres.items():
                    if _add_to_staging(genre, uris):
                        added += 1
                st.success(f"Added {added} genre playlists to staging.")

        # Filter genres
        allowed = GENRE_FAMILIES[family_filter]
        display_genres = {
            g: uris for g, uris in valid_genres.items()
            if allowed is None or g in allowed
        }
        display_genres = dict(sorted(display_genres.items(), key=lambda x: -len(x[1])))

        if not display_genres:
            st.info("No genres match this filter.")
        else:
            for genre, uris in display_genres.items():
                cohesion = _cohesion_for_uris(uris)
                col1, col2, col3, col4 = st.columns([4, 1, 1, 2])
                with col1:
                    st.markdown(f"**{genre}**")
                with col2:
                    st.write(f"{len(uris)} tracks")
                with col3:
                    st.write(f"{cohesion * 100:.0f}% cohesion")
                with col4:
                    if st.button("Add to Staging", key=f"genre_stage_{genre}", use_container_width=True):
                        pid = _add_to_staging(genre, uris)
                        if pid:
                            st.success(f"Added **{genre}** to staging.")

# ── TAB: Eras ─────────────────────────────────────────────────────────────────
with tab_eras:
    valid_eras = {e: uris for e, uris in era_map.items() if len(uris) >= MIN_ERA}
    if not valid_eras:
        st.info(f"Not enough tracks per era (minimum {MIN_ERA} required).")
    else:
        st.write(f"**{len(valid_eras)} eras** found in your library.")
        sorted_eras = sorted(valid_eras.items(), key=lambda x: x[0])
        for era, uris in sorted_eras:
            cohesion = _cohesion_for_uris(uris)
            col1, col2, col3, col4 = st.columns([4, 1, 1, 2])
            with col1:
                st.markdown(f"**{era}**")
            with col2:
                st.write(f"{len(uris)} tracks")
            with col3:
                st.write(f"{cohesion * 100:.0f}% cohesion")
            with col4:
                if st.button("Add to Staging", key=f"era_stage_{era}", use_container_width=True):
                    pid = _add_to_staging(era, uris, playlist_type="era")
                    if pid:
                        st.success(f"Added **{era}** to staging.")

# ── TAB: Languages ────────────────────────────────────────────────────────────
with tab_languages:
    st.write("Group your tracks by detected lyric language (based on track names — approximate).")
    if st.button("Detect Languages", type="secondary"):
        with st.spinner("Detecting languages..."):
            try:
                from core.language import group_by_language, language_display_name
                lang_groups = group_by_language(all_tracks, min_tracks=5)
                st.session_state["lang_groups"] = lang_groups
            except Exception as e:
                st.error(f"Language detection failed: {e}")

    lang_groups = st.session_state.get("lang_groups", {})
    if lang_groups:
        for lang_code, uris in sorted(lang_groups.items(), key=lambda x: -len(x[1])):
            if lang_code == "other":
                continue
            try:
                from core.language import language_display_name
                lang_name = language_display_name(lang_code)
            except Exception:
                lang_name = lang_code.upper()

            cohesion = _cohesion_for_uris(uris)
            col1, col2, col3, col4 = st.columns([4, 1, 1, 2])
            with col1:
                st.markdown(f"**{lang_name}**")
            with col2:
                st.write(f"{len(uris)} tracks")
            with col3:
                st.write(f"{cohesion * 100:.0f}% cohesion")
            with col4:
                if st.button(
                    "Add to Staging",
                    key=f"lang_stage_{lang_code}",
                    use_container_width=True,
                ):
                    pid = _add_to_staging(f"{lang_name} Songs", uris, playlist_type="genre")
                    if pid:
                        st.success(f"Added **{lang_name} Songs** to staging.")
    elif not lang_groups and "lang_groups" in st.session_state:
        st.info("No language groups found with 5+ tracks.")
