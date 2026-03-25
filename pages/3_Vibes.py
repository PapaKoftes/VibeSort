"""
pages/3_Vibes.py — Main vibes discovery interface.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort — Vibes",
    page_icon="🎧",
    layout="wide",
)

# Guard: require auth
if not st.session_state.get("spotify_token"):
    st.warning("Please connect to Spotify first.")
    if st.button("Connect"):
        st.switch_page("pages/1_Connect.py")
    st.stop()

# Guard: require scan
if not st.session_state.get("vibesort"):
    st.info("Scan your library first to discover vibes.")
    if st.button("Scan Library"):
        st.switch_page("pages/2_Scan.py")
    st.stop()

vibesort = st.session_state["vibesort"]
mood_results: dict = vibesort.get("mood_results", {})
profiles: dict = vibesort.get("profiles", {})

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Vibes")
    st.metric("Moods found", len(mood_results))
    try:
        from staging import staging as _staging_mod
        staged_count = _staging_mod.get_staged_count()
    except Exception:
        staged_count = len(st.session_state.get("staged_ids", []))
    st.metric("Staged", staged_count)

    st.divider()
    naming_mode = st.selectbox(
        "Naming mode",
        ["Middle-out (default)", "Top-down", "Bottom-up"],
        index=0,
    )

    st.divider()
    if st.button("Go to Staging Shelf", use_container_width=True):
        st.switch_page("pages/7_Staging.py")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _audio_mean(uris):
    vectors = [profiles[u]["audio_vector"] for u in uris if u in profiles and profiles[u].get("audio_vector")]
    if not vectors:
        return [0.5] * 6
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(6)]


def _genre_count(uris):
    counts = {}
    for u in uris:
        p = profiles.get(u, {})
        for macro in p.get("macro_genres", ["Other"]):
            counts[macro] = counts.get(macro, 0) + 1
    return counts


def _generate_name(mood_name, uris):
    genre_counts = _genre_count(uris)
    audio = _audio_mean(uris)
    try:
        from core.namer import middle_out_name, bottom_up_name, top_down_name
        if "Middle-out" in naming_mode:
            name, desc = middle_out_name(
                [profiles[u] for u in uris if u in profiles],
                mood_name=mood_name,
            )
        elif "Top-down" in naming_mode:
            name, desc = top_down_name(mood_name, [profiles[u] for u in uris if u in profiles])
        else:
            name, desc = bottom_up_name([profiles[u] for u in uris if u in profiles])
        return name, desc
    except Exception:
        return mood_name, f"{len(uris)} tracks"


def _top_tracks_display(uris, n=3):
    rows = []
    for uri in uris[:n]:
        p = profiles.get(uri, {})
        if p:
            artists = ", ".join(p.get("artists", [])[:2])
            rows.append(f"**{p.get('name', '')}** — {artists}")
    return rows


def _add_to_staging(mood_name, uris, suggested_name, description, expand_recs):
    """Add a mood playlist to the staging shelf."""
    try:
        import uuid
        from datetime import datetime, timezone
        from staging import staging

        genre_counts = _genre_count(uris)
        total = sum(genre_counts.values()) or 1
        genre_breakdown = {g: round(c / total, 3) for g, c in genre_counts.items()}
        cohesion = mood_results.get(mood_name, {}).get("cohesion", 0.0)

        data = {
            "suggested_name":  suggested_name,
            "user_name":       suggested_name,
            "description":     description,
            "track_uris":      list(uris),
            "rec_uris":        [],
            "playlist_type":   "mood",
            "source_type":     "mood",
            "source_label":    mood_name,
            "genre_breakdown": genre_breakdown,
            "cohesion":        cohesion,
            "expand_with_recs": expand_recs,
        }
        playlist_id = staging.save(data)
        # Track staged IDs in session state
        if "staged_ids" not in st.session_state:
            st.session_state["staged_ids"] = []
        if playlist_id not in st.session_state["staged_ids"]:
            st.session_state["staged_ids"].append(playlist_id)
        return playlist_id
    except Exception as e:
        st.error(f"Could not save to staging: {e}")
        return None


# ── Main page ─────────────────────────────────────────────────────────────────

st.title("Your Vibes")

if not mood_results:
    st.info("No moods found. Your library may be too small or not yet scanned.")
    if st.button("Re-scan"):
        st.switch_page("pages/2_Scan.py")
    st.stop()

# Search/filter
search = st.text_input("Filter by mood name or keyword", placeholder="e.g. dark, lo-fi, rap...")

# Sort by cohesion
sorted_moods = sorted(mood_results.items(), key=lambda x: -x[1]["cohesion"])

if search:
    query = search.lower()
    sorted_moods = [
        (name, info) for name, info in sorted_moods
        if query in name.lower()
    ]

st.write(f"Showing **{len(sorted_moods)}** moods")
st.write("")

# Track which mood card is expanded
if "expanded_vibe" not in st.session_state:
    st.session_state["expanded_vibe"] = None

# Grid: 3 columns
cols_per_row = 3
for row_start in range(0, len(sorted_moods), cols_per_row):
    row_moods = sorted_moods[row_start: row_start + cols_per_row]
    cols = st.columns(cols_per_row)

    for col, (mood_name, info) in zip(cols, row_moods):
        with col:
            uris = info["uris"]
            cohesion = info["cohesion"]
            count = info["count"]

            # Card container
            with st.container(border=True):
                st.markdown(f"### {mood_name}")
                try:
                    from core.mood_graph import get_mood
                    pack = get_mood(mood_name) or {}
                    desc = pack.get("description", "")
                    if desc:
                        st.caption(desc)
                except Exception:
                    pass

                st.write(f"{count} tracks · {cohesion * 100:.0f}% cohesion")
                st.progress(cohesion, text="")

                top = _top_tracks_display(uris, n=3)
                for t in top:
                    st.markdown(f"- {t}")

                expand_key = f"expand_{mood_name}"
                is_expanded = st.session_state.get("expanded_vibe") == mood_name

                if st.button(
                    "Hide" if is_expanded else "View & Stage",
                    key=f"btn_{mood_name}",
                    use_container_width=True,
                ):
                    st.session_state["expanded_vibe"] = None if is_expanded else mood_name
                    st.rerun()

    # Show expanded card below the row
    for mood_name, info in row_moods:
        if st.session_state.get("expanded_vibe") == mood_name:
            uris = info["uris"]
            st.divider()
            st.markdown(f"#### {mood_name} — Full Tracklist ({len(uris)} tracks)")

            # Show all tracks
            track_rows = []
            for uri in uris:
                p = profiles.get(uri, {})
                if p:
                    artists = ", ".join(p.get("artists", [])[:2])
                    track_rows.append(f"**{p.get('name', '')}** — {artists}")
            for i in range(0, len(track_rows), 3):
                chunk = track_rows[i:i+3]
                tcols = st.columns(3)
                for tc, row in zip(tcols, chunk):
                    tc.markdown(f"- {row}")

            st.divider()
            st.markdown("**Add to Staging**")

            suggested_name, suggested_desc = _generate_name(mood_name, uris)

            col_a, col_b = st.columns(2)
            with col_a:
                user_name = st.text_input(
                    "Playlist name",
                    value=suggested_name,
                    key=f"name_{mood_name}",
                )
            with col_b:
                user_desc = st.text_area(
                    "Description",
                    value=suggested_desc,
                    key=f"desc_{mood_name}",
                    height=80,
                )

            expand_recs = st.toggle(
                "Expand with similar songs (recommendations)",
                value=True,
                key=f"recs_{mood_name}",
            )

            if st.button(
                "Save to Staging Shelf",
                type="primary",
                key=f"stage_{mood_name}",
                use_container_width=True,
            ):
                pid = _add_to_staging(mood_name, uris, user_name, user_desc, expand_recs)
                if pid:
                    st.success(f"Added **{user_name}** to staging shelf.")
            st.divider()
            break
