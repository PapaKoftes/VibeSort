"""
pages/6_Blend.py — Multi-user Vibesort Blend page.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort — Blend",
    page_icon="🎧",
    layout="wide",
)

if not st.session_state.get("spotify_token"):
    st.warning("Please connect to Spotify first.")
    if st.button("Connect"):
        st.switch_page("pages/1_Connect.py")
    st.stop()

# ── Page ─────────────────────────────────────────────────────────────────────

st.title("Blend")
st.write(
    "Better than Spotify Blend: supports 3+ users, genre-aware, and generates multiple playlist angles. "
    "Paste Spotify playlist URLs to represent each user's library."
)

vibesort = st.session_state.get("vibesort")
if not vibesort:
    st.warning(
        "Your library hasn't been scanned yet. "
        "Blend works best when your own library is scanned first — but you can still use it without."
    )

sp = st.session_state.get("sp")

# Input: playlist URLs
st.subheader("User Playlists")
st.write("Paste 2–4 Spotify playlist URLs (one per line). Each URL represents one user's library.")
urls_input = st.text_area(
    "Playlist URLs",
    placeholder=(
        "https://open.spotify.com/playlist/...\n"
        "https://open.spotify.com/playlist/..."
    ),
    height=120,
)

if "blend_results" not in st.session_state:
    st.session_state["blend_results"] = []

if st.button("Find Common Ground", type="primary", use_container_width=False):
    urls = [u.strip() for u in urls_input.strip().splitlines() if u.strip()]
    if len(urls) < 2:
        st.error("Please enter at least 2 playlist URLs.")
    elif len(urls) > 4:
        st.error("Maximum 4 playlists supported.")
    else:
        with st.spinner("Fetching playlists and computing blend..."):
            try:
                from core.blend import fetch_user_library, blend_profiles, generate_blend_playlists
                import config as cfg

                user_profiles = []
                for i, url in enumerate(urls):
                    tracks = fetch_user_library(sp, [url])
                    user_profiles.append((f"User {i+1}", tracks))

                # Merge all profiles
                combined = {}
                for _, profs in user_profiles:
                    combined.update(profs)

                # If own library is scanned, add it to first user's profiles
                if vibesort:
                    own_profiles = vibesort.get("profiles", {})
                    if own_profiles:
                        user_profiles[0] = (
                            "You",
                            {**user_profiles[0][1], **own_profiles},
                        )
                        combined.update(own_profiles)

                playlists = generate_blend_playlists(sp, user_profiles, combined, cfg)
                st.session_state["blend_results"] = playlists
                st.session_state["blend_user_profiles"] = user_profiles
                st.session_state["blend_combined"] = combined

                if playlists:
                    st.success(f"Generated {len(playlists)} blend playlists.")
                else:
                    st.warning("No overlap found between the provided playlists.")

            except Exception as e:
                st.error(f"Blend failed: {e}")
                st.exception(e)

# ── Results ───────────────────────────────────────────────────────────────────

blend_results = st.session_state.get("blend_results", [])
blend_combined = st.session_state.get("blend_combined", {})

if blend_results:
    st.divider()
    st.subheader("Blend Results")

    # Audio comparison chart
    user_profiles_data = st.session_state.get("blend_user_profiles", [])
    if len(user_profiles_data) >= 2 and blend_combined:
        st.markdown("**Audio Fingerprint Comparison**")
        chart_data = {}
        labels = ["Energy", "Valence", "Dance", "Acoustic", "Instrumental"]
        for username, profs in user_profiles_data:
            uris = list(profs.keys())
            vectors = [
                blend_combined[u]["audio_vector"]
                for u in uris
                if u in blend_combined and blend_combined[u].get("audio_vector")
            ]
            if vectors:
                n = len(vectors)
                mean = [sum(v[i] for v in vectors) / n for i in range(6)]
                chart_data[username] = {
                    "Energy": round(mean[0], 2),
                    "Valence": round(mean[1], 2),
                    "Dance": round(mean[2], 2),
                    "Acoustic": round(mean[4], 2),
                    "Instrumental": round(mean[5], 2),
                }

        if chart_data:
            try:
                import pandas as pd
                df = pd.DataFrame(chart_data, index=labels)
                st.bar_chart(df)
            except Exception:
                for username, vals in chart_data.items():
                    st.write(f"**{username}:** {vals}")

    st.divider()

    for playlist in blend_results:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### {playlist['suggested_name']}")
                st.caption(playlist.get("description", ""))
                track_count = len(playlist.get("track_uris", []))
                cohesion = playlist.get("cohesion", 0.0)
                st.write(f"{track_count} tracks · {cohesion * 100:.0f}% cohesion")

                # Genre breakdown
                genre_bd = playlist.get("genre_breakdown", {})
                if genre_bd:
                    top_genres = sorted(genre_bd.items(), key=lambda x: -x[1])[:3]
                    genre_str = " · ".join(
                        f"{g} ({int(v*100)}%)" for g, v in top_genres if g != "Other"
                    )
                    st.caption(genre_str)

            with col2:
                st.write("")
                if st.button(
                    "Add to Staging",
                    key=f"blend_stage_{playlist['suggested_name']}",
                    use_container_width=True,
                ):
                    try:
                        from staging import staging
                        pid = staging.save(playlist)
                        if "staged_ids" not in st.session_state:
                            st.session_state["staged_ids"] = []
                        if pid not in st.session_state["staged_ids"]:
                            st.session_state["staged_ids"].append(pid)
                        st.success("Added to staging.")
                    except Exception as e:
                        st.error(f"Could not save: {e}")

    st.divider()
    if st.button("Go to Staging Shelf", use_container_width=True):
        st.switch_page("pages/7_Staging.py")
