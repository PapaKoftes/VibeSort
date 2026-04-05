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
from core.theme import inject, render_scan_quality_strip
inject()

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

    from core.audio_groups import has_real_audio
    _audio_note = (
        "✓ real audio features"
        if has_real_audio(profiles)
        else "⚠ tempo from genres + Discogs styles (no Spotify BPM)"
    )
    st.caption(_audio_note)

    st.divider()
    if st.button("Go to Staging Shelf", use_container_width=True):
        st.switch_page("pages/7_Staging.py")


# ── Helpers ───────────────────────────────────────────────────────────────────

GENRE_FAMILIES = {
    "All":        None,
    "Rap / Hip-Hop": ["East Coast Rap", "West Coast Rap", "Southern Rap", "Houston Rap",
                      "Midwest Rap", "UK Rap / Grime", "French Rap", "Phonk",
                      "Brazilian Phonk"],
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
    "Ambient": ["Ambient / Experimental", "Electronic / Ambient"],
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
render_scan_quality_strip(vibesort)
st.write("")

tab_genres, tab_eras, tab_languages, tab_tempo, tab_character = st.tabs([
    "Genres", "Eras / Decades", "Languages", "Tempo / BPM", "Sound Character",
])

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
    _ly_map = vibesort.get("lyrics_language_map") or {}
    if _ly_map:
        st.success(
            "Using **lyric text language** from your last scan (per track, from analysed lyrics). "
            "This is more reliable than guessing from titles."
        )
        if st.button("Build language groups from lyrics", type="primary"):
            with st.spinner("Grouping…"):
                try:
                    from core.language import group_by_lyrics_language

                    st.session_state["lang_groups"] = group_by_lyrics_language(
                        all_tracks, _ly_map, min_tracks=5
                    )
                except Exception as e:
                    st.error(f"Failed: {e}")
    else:
        st.info(
            "No lyric language map in this scan — run a scan with lyrics enrichment, "
            "or use title-based detection below (less accurate)."
        )

    st.caption("Fallback: detect from track + artist names (short titles often stay *Unknown*).")
    if st.button("Detect from titles (fallback)", type="secondary"):
        with st.spinner("Detecting languages..."):
            try:
                from core.language import group_by_language

                st.session_state["lang_groups"] = group_by_language(all_tracks, min_tracks=5)
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

# ── TAB: Tempo / BPM ──────────────────────────────────────────────────────────
with tab_tempo:
    from core.audio_groups import tempo_groups, energy_groups, has_real_audio

    _has_audio = has_real_audio(profiles)
    if not _has_audio:
        st.info(
            "⚠️ **Spotify BPM data is unavailable** (audio-features endpoint removed). "
            "Tempo bands use **macro genres** plus **Discogs-style tags** when present "
            "(e.g. trap → Cruise, shoegaze → Slow Burn, techno → Rush) — not measured BPM.",
        )

    # ── BPM bands ─────────────────────────────────────────────────────────────
    st.subheader("BPM Range Playlists")
    st.caption("Group your library by tempo — great for workouts, DJ prep, or running playlists.")

    _t_groups = tempo_groups(profiles, min_tracks=MIN_GENRE)
    _src = next(iter(_t_groups.values()), {}).get("source", "") if _t_groups else ""
    _source_label = {
        "audio_features": "exact BPM",
        "genre_and_style_inference": "genres + Discogs styles",
        "genre_inference": "macro genres",
    }.get(_src, "exact BPM" if _has_audio else "inferred")
    if not _t_groups:
        st.info(f"Not enough tracks per tempo band (minimum {MIN_GENRE} needed).")
    else:
        for band_label, info in _t_groups.items():
            uris        = info["uris"]
            bpm_range   = info["bpm_range"]
            description = info["description"]
            col1, col2, col3 = st.columns([4, 3, 2])
            with col1:
                st.markdown(f"**{band_label}** &nbsp; `{bpm_range}`")
                st.caption(description)
            with col2:
                st.write(f"{len(uris)} tracks")
                st.caption(f"via {_source_label}")
            with col3:
                if st.button(
                    "Add to Staging",
                    key=f"tempo_stage_{band_label}",
                    use_container_width=True,
                ):
                    pid = _add_to_staging(band_label, uris, playlist_type="tempo")
                    if pid:
                        st.success(f"Added **{band_label}** to staging.")

    st.divider()

    # ── Energy bands ──────────────────────────────────────────────────────────
    st.subheader("Uptempo / Downtempo")
    st.caption("Filter by energy level — from ambient chill to maximum intensity.")

    _e_groups = energy_groups(profiles, min_tracks=MIN_GENRE)
    _energy_src_label = "audio features" if _has_audio else "macro genres"
    if not _e_groups:
        st.info(f"Not enough tracks per energy band (minimum {MIN_GENRE} needed).")
    else:
        _ENERGY_ICONS = {
            "Downtempo":   "🌙",
            "Mid Energy":  "🌤",
            "Uptempo":     "⚡",
            "High Energy": "🔥",
        }
        for band_label, info in _e_groups.items():
            uris        = info["uris"]
            description = info["description"]
            icon        = _ENERGY_ICONS.get(band_label, "")
            col1, col2, col3 = st.columns([4, 3, 2])
            with col1:
                st.markdown(f"{icon} **{band_label}**")
                st.caption(description)
            with col2:
                st.write(f"{len(uris)} tracks")
                st.caption(f"via {_energy_src_label}")
            with col3:
                if st.button(
                    "Add to Staging",
                    key=f"energy_stage_{band_label}",
                    use_container_width=True,
                ):
                    pid = _add_to_staging(band_label, uris, playlist_type="energy")
                    if pid:
                        st.success(f"Added **{band_label}** to staging.")

# ── TAB: Sound Character ──────────────────────────────────────────────────────
with tab_character:
    from core.audio_groups import character_groups, has_real_audio as _has_real_audio_char

    _has_audio_char = _has_real_audio_char(profiles)
    if not _has_audio_char:
        st.info(
            "⚠️ **Spotify audio features unavailable** (Dev Mode restriction). "
            "Character playlists are built using **genre inference** and will be "
            "approximate. Instrumental detection requires real `instrumentalness` "
            "data from Spotify.",
        )

    st.subheader("Sound Character Playlists")
    st.caption(
        "Curate by how music *sounds*, not just what genre it is. "
        "A track can appear in multiple groups (an acoustic piano piece is both Acoustic and Instrumental)."
    )

    _char_groups = character_groups(profiles, min_tracks=MIN_GENRE)

    if not _char_groups:
        if _has_audio_char:
            st.info(f"Not enough tracks per character group (minimum {MIN_GENRE} needed).")
        else:
            st.warning(
                "No character groups found via genre inference — your library may not have "
                "enough tracks in acoustic/instrumental/electronic genres. "
                "These groups work best with Spotify audio features enabled."
            )
    else:
        _CHAR_ICONS = {
            "Acoustic":             "🎸",
            "Instrumental":         "🎹",
            "Electronic":           "🎛️",
            "Vocal-Forward":        "🎤",
            "Heavy & Distorted":    "🔊",
            "Atmospheric & Wide":   "🌫️",
            "Groove & Rhythm":      "🥁",
        }
        _source_label_char = "acousticness/instrumentalness" if _has_audio_char else "genre inference"
        for char_label, info in _char_groups.items():
            uris        = info["uris"]
            description = info["description"]
            icon        = _CHAR_ICONS.get(char_label, "🎵")
            cohesion    = _cohesion_for_uris(uris)

            col1, col2, col3, col4 = st.columns([4, 2, 1, 2])
            with col1:
                st.markdown(f"{icon} **{char_label}**")
                st.caption(description)
            with col2:
                st.write(f"{len(uris)} tracks")
                st.caption(f"via {_source_label_char}")
            with col3:
                st.write(f"{cohesion * 100:.0f}% cohesion")
            with col4:
                if st.button(
                    "Add to Staging",
                    key=f"char_stage_{char_label}",
                    use_container_width=True,
                ):
                    pid = _add_to_staging(char_label, uris, playlist_type="character")
                    if pid:
                        st.success(f"Added **{char_label}** to staging.")
