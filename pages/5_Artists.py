"""
pages/5_Artists.py — Artist playlists page.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort — Artists",
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
artist_map: dict = vibesort.get("artist_map", {})
artist_genres: dict = vibesort.get("artist_genres", {})

# Sorted by track count
sorted_artists = sorted(artist_map.items(), key=lambda x: -len(x[1]))

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Artists")
    st.metric("Artists with 8+ songs", len(sorted_artists))

    st.divider()
    if st.button("Go to Staging Shelf", use_container_width=True):
        st.switch_page("pages/7_Staging.py")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _top_genres_for_artist(artist_name: str) -> list[str]:
    """Get top macro genres for an artist from the artist_genres map."""
    for raw_genres in artist_genres.values():
        # artist_genres is {artist_id: [genre_str, ...]}; we need to look up by name
        pass
    # Collect from profiles
    counts = {}
    for uri in artist_map.get(artist_name, []):
        p = profiles.get(uri, {})
        if not p:
            continue
        # Only include this track if the artist is one of its artists
        if artist_name in p.get("artists", []):
            for macro in p.get("macro_genres", []):
                counts[macro] = counts.get(macro, 0) + 1
    return [g for g, _ in sorted(counts.items(), key=lambda x: -x[1])[:3]]


def _genre_breakdown_for_uris(uris):
    counts = {}
    for u in uris:
        p = profiles.get(u, {})
        for macro in p.get("macro_genres", ["Other"]):
            counts[macro] = counts.get(macro, 0) + 1
    return counts


def _add_artist_to_staging(artist_name, uris):
    try:
        from staging import staging
        from core.namer import bottom_up_name

        track_profiles_list = [profiles[u] for u in uris if u in profiles]
        name, desc = bottom_up_name(track_profiles_list)
        # For single-artist playlists, always use the artist name
        name = artist_name
        desc = f"Everything in your library by {artist_name}. {len(uris)} tracks."

        genre_bd = _genre_breakdown_for_uris(uris)
        total = sum(genre_bd.values()) or 1
        genre_bd_pct = {g: round(c / total, 3) for g, c in genre_bd.items()}

        data = {
            "suggested_name":  name,
            "user_name":       name,
            "description":     desc,
            "track_uris":      list(uris),
            "rec_uris":        [],
            "playlist_type":   "artist",
            "genre_breakdown": genre_bd_pct,
            "cohesion":        0.85,
            "expand_with_recs": False,
            "metadata":        {"source_artist": artist_name},
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

st.title("Artist Playlists")

if not sorted_artists:
    st.info("No artists with 8+ songs found. Your library may need more tracks.")
    st.stop()

# Selection state
if "selected_artists" not in st.session_state:
    st.session_state["selected_artists"] = set()

# Select all / deselect all
col_sel, col_desel, col_addsel, _ = st.columns([2, 2, 3, 5])
with col_sel:
    if st.button("Select All", use_container_width=True):
        st.session_state["selected_artists"] = {a for a, _ in sorted_artists}
        st.rerun()
with col_desel:
    if st.button("Deselect All", use_container_width=True):
        st.session_state["selected_artists"] = set()
        st.rerun()
with col_addsel:
    selected = st.session_state["selected_artists"]
    if selected:
        if st.button(
            f"Add {len(selected)} Selected to Staging",
            type="primary",
            use_container_width=True,
        ):
            added = 0
            for artist_name in selected:
                uris = artist_map.get(artist_name, [])
                if uris and _add_artist_to_staging(artist_name, uris):
                    added += 1
            st.success(f"Added {added} artist playlists to staging.")
            st.session_state["selected_artists"] = set()
            st.rerun()

st.divider()

# Artist rows
for artist_name, uris in sorted_artists:
    top_genres = _top_genres_for_artist(artist_name)
    genres_str = " · ".join(top_genres[:2]) if top_genres else "—"

    col1, col2, col3, col4, col5 = st.columns([3, 1, 3, 2, 2])
    with col1:
        is_selected = artist_name in st.session_state["selected_artists"]
        checked = st.checkbox(
            f"**{artist_name}**",
            value=is_selected,
            key=f"chk_{artist_name}",
        )
        if checked and artist_name not in st.session_state["selected_artists"]:
            st.session_state["selected_artists"].add(artist_name)
        elif not checked and artist_name in st.session_state["selected_artists"]:
            st.session_state["selected_artists"].discard(artist_name)
    with col2:
        st.write(f"{len(uris)} tracks")
    with col3:
        st.caption(genres_str)
    with col4:
        pass
    with col5:
        if st.button("Add to Staging", key=f"artist_stage_{artist_name}", use_container_width=True):
            pid = _add_artist_to_staging(artist_name, uris)
            if pid:
                st.success(f"Added **{artist_name}** to staging.")
