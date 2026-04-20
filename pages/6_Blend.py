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
from core.theme import inject
inject()

if not st.session_state.get("spotify_token"):
    st.warning("Please connect to Spotify first.")
    if st.button("Connect"):
        st.switch_page("pages/1_Connect.py")
    st.stop()

# ── Page ─────────────────────────────────────────────────────────────────────

st.title("Blend")
st.write(
    "Merge multiple libraries into shared playlists. Supports 3+ users, genre-aware, "
    "and generates multiple playlist angles. Paste Spotify playlist URLs to represent each person's library."
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
                from core.blend import fetch_user_library, generate_blend_playlists
                import config as cfg

                # fetch_user_library() returns simplified track dicts.
                # generate_blend_playlists() expects profile-format dicts
                # with audio_vector and macro_genres — build minimal ones so
                # audio scoring and genre-overlap logic work correctly.
                from core import profile as _profile_mod
                from core.genre import to_macro as _to_macro

                def _minimal_profile(track_dict: dict, artist_genres_by_name: dict = None) -> dict:
                    """Wrap a raw track dict in the minimal profile shape."""
                    # Build real macro_genres from Deezer-enriched artist data if available
                    macro_genres = []
                    if artist_genres_by_name:
                        _seen: set[str] = set()
                        for _a in track_dict.get("artists", []):
                            _aname = (_a if isinstance(_a, str) else _a.get("name", "")).lower().strip()
                            for _genre in artist_genres_by_name.get(_aname, []):
                                _macro = _to_macro(_genre)
                                if _macro not in _seen:
                                    _seen.add(_macro)
                                    macro_genres.append(_macro)
                    return {
                        "uri":          track_dict.get("uri", ""),
                        "name":         track_dict.get("name", ""),
                        "artists":      track_dict.get("artists", []),
                        "audio_vector": [0.5] * 6,   # neutral — no audio features for other users
                        "raw_genres":   [],
                        "macro_genres": macro_genres or ["Other"],
                        "tags":         {},
                        "popularity":   track_dict.get("popularity", 50),
                    }

                # Collect all external tracks first so we can batch-enrich genres
                user_raw_tracks: list[tuple[str, dict]] = []
                for i, url in enumerate(urls):
                    raw_tracks = fetch_user_library(sp, [url])
                    user_raw_tracks.append((f"User {i+1}", raw_tracks))

                # ── Deezer genre enrichment for external tracks ───────────────
                # Collect unique artist names across all external playlists,
                # enrich via Deezer, then pass the result to _minimal_profile()
                # so genre-overlap playlists work for Blend users too.
                _blend_artist_genres_by_name: dict[str, list[str]] = {}
                try:
                    from core import deezer as _dz_blend

                    # Build artist-name frequency map (name_lower → (name, count))
                    _blend_artist_freq: dict[str, tuple[str, int]] = {}
                    for _, _rt in user_raw_tracks:
                        for _t in _rt.values():
                            for _a in _t.get("artists", []):
                                _aname = _a if isinstance(_a, str) else ""
                                if _aname:
                                    _akey = _aname.lower().strip()
                                    _prev = _blend_artist_freq.get(_akey, (_aname, 0))[1]
                                    _blend_artist_freq[_akey] = (_aname, _prev + 1)

                    # enrich_artists() expects {artist_id: (name, count)} but Blend
                    # tracks have no Spotify artist IDs — use name as key instead.
                    _dz_freq_for_blend = {k: v for k, v in _blend_artist_freq.items()}
                    _dz_blend_result = _dz_blend.enrich_artists(
                        _dz_freq_for_blend,
                        existing_genres={},
                        max_artists=150,
                        progress_fn=None,
                    )
                    # Result is keyed by the same key we passed in (artist_name_lower)
                    _blend_artist_genres_by_name = {
                        k: v for k, v in _dz_blend_result.items() if v
                    }
                except Exception:
                    pass  # Genre enrichment optional — fall back to "Other"

                user_profiles = []
                for label, raw_tracks in user_raw_tracks:
                    profiles_for_user = {
                        uri: _minimal_profile(t, _blend_artist_genres_by_name)
                        for uri, t in raw_tracks.items()
                    }
                    user_profiles.append((label, profiles_for_user))

                # Merge all profiles
                combined = {}
                for _, profs in user_profiles:
                    combined.update(profs)

                # If own library is scanned, replace User 1 with the real scanned
                # profiles — these have proper audio_vector, macro_genres, and tags,
                # so genre-overlap and audio-scoring will actually work.
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
        st.switch_page("pages/8_Staging.py")
