"""
pages/7_Staging.py — The staging shelf.
The most important UI page: review, rename, and deploy playlists to Spotify.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort — Staging",
    page_icon="🎧",
    layout="wide",
)

if not st.session_state.get("spotify_token"):
    st.warning("Please connect to Spotify first.")
    if st.button("Connect"):
        st.switch_page("pages/1_Connect.py")
    st.stop()

sp = st.session_state.get("sp")
me = st.session_state.get("me", {})
user_id = me.get("id", "")
vibesort = st.session_state.get("vibesort", {})
profiles = vibesort.get("profiles", {}) if vibesort else {}

try:
    from staging import staging
except Exception as e:
    st.error(f"Could not load staging module: {e}")
    st.stop()

try:
    import config as cfg
except Exception:
    cfg = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _track_display(uri: str) -> str:
    p = profiles.get(uri, {})
    if p:
        artists = ", ".join(p.get("artists", [])[:2])
        return f"{p.get('name', uri)} — {artists}"
    return uri


def _deploy_one(staged: dict) -> tuple[bool, str]:
    """Deploy a single staged playlist. Returns (success, url_or_error)."""
    try:
        from core.deploy import deploy_one
        existing_uris = vibesort.get("existing_uris") if vibesort else None
        url = deploy_one(sp, user_id, staged, profiles=profiles, existing_uris=existing_uris)
        return True, url
    except Exception as e:
        return False, str(e)


def _deploy_all(staged_list: list) -> list[dict]:
    """Deploy all staged playlists."""
    try:
        from core.deploy import deploy_all
        existing_uris = vibesort.get("existing_uris") if vibesort else None
        return deploy_all(sp, user_id, staged_list, profiles=profiles, existing_uris=existing_uris)
    except Exception as e:
        return [{"name": "All", "url": None, "success": False, "error": str(e)}]


# ── Main page ─────────────────────────────────────────────────────────────────

st.title("Staging Shelf")

# Load all pending playlists
try:
    staged_playlists = staging.load_all()
except Exception as e:
    st.error(f"Could not load staging shelf: {e}")
    staged_playlists = []

# ── Empty state ───────────────────────────────────────────────────────────────
if not staged_playlists:
    st.info(
        "Your staging shelf is empty. "
        "Go to Vibes, Genres, or Artists to discover and add playlists."
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Browse Vibes", use_container_width=True):
            st.switch_page("pages/3_Vibes.py")
    with col2:
        if st.button("Browse Genres", use_container_width=True):
            st.switch_page("pages/4_Genres.py")
    with col3:
        if st.button("Browse Artists", use_container_width=True):
            st.switch_page("pages/5_Artists.py")
    st.stop()

# ── Header with Deploy All ────────────────────────────────────────────────────
col_count, col_btn = st.columns([3, 2])
with col_count:
    st.write(f"**{len(staged_playlists)} playlists ready to deploy**")
with col_btn:
    deploy_all_clicked = st.button(
        f"Deploy All {len(staged_playlists)} to Spotify",
        type="primary",
        use_container_width=True,
    )

if deploy_all_clicked:
    if not user_id:
        st.error("Could not determine your Spotify user ID. Please reconnect.")
    else:
        with st.spinner(f"Deploying {len(staged_playlists)} playlists..."):
            results = _deploy_all(staged_playlists)
        st.divider()
        st.subheader("Deploy Results")
        for r in results:
            if r["success"]:
                st.success(f"**{r['name']}** — [Open in Spotify]({r['url']})")
            else:
                st.error(f"**{r['name']}** — Failed: {r['error']}")
        st.divider()
        # Refresh staged list
        try:
            staged_playlists = staging.load_all()
        except Exception:
            staged_playlists = []

st.divider()

# Track which remove confirmation is pending
if "remove_confirm" not in st.session_state:
    st.session_state["remove_confirm"] = None

# ── Playlist cards ────────────────────────────────────────────────────────────
for staged in staged_playlists:
    pid = staged["id"]
    track_uris = staged.get("track_uris", [])
    rec_uris   = staged.get("rec_uris", [])
    cohesion   = staged.get("cohesion", 0.0)
    genre_bd   = staged.get("genre_breakdown", {})
    ptype      = staged.get("playlist_type", "genre")

    with st.container(border=True):
        # Header row
        hcol1, hcol2 = st.columns([4, 2])
        with hcol1:
            new_name = st.text_input(
                "Playlist name",
                value=staged.get("user_name") or staged.get("suggested_name", "Untitled"),
                key=f"name_{pid}",
                label_visibility="collapsed",
            )
            if new_name != (staged.get("user_name") or staged.get("suggested_name", "")):
                try:
                    staging.update(pid, {"user_name": new_name})
                except Exception:
                    pass
        with hcol2:
            st.caption(f"{ptype.upper()} · {len(track_uris)} tracks · {cohesion * 100:.0f}% cohesion")

        # Description
        new_desc = st.text_area(
            "Description",
            value=staged.get("description", ""),
            key=f"desc_{pid}",
            height=68,
            label_visibility="collapsed",
        )
        if new_desc != staged.get("description", ""):
            try:
                staging.update(pid, {"description": new_desc})
            except Exception:
                pass

        # Genre breakdown bar
        if genre_bd:
            top_genres = sorted(genre_bd.items(), key=lambda x: -x[1])[:4]
            genre_str = "  ".join(
                f"`{g}` {int(v*100)}%" for g, v in top_genres if g != "Other"
            )
            if genre_str:
                st.markdown(genre_str)

        # Controls row
        ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([3, 2, 2, 2])
        with ctrl_col1:
            expand_recs = st.toggle(
                "Expand with recs",
                value=staged.get("expand_with_recs", True),
                key=f"recs_{pid}",
            )
            if expand_recs != staged.get("expand_with_recs"):
                try:
                    staging.update(pid, {"expand_with_recs": expand_recs})
                except Exception:
                    pass

        # Track preview expander
        with st.expander(f"Preview {len(track_uris)} tracks"):
            for uri in track_uris[:50]:
                st.markdown(f"- {_track_display(uri)}")
            if len(track_uris) > 50:
                st.caption(f"... and {len(track_uris) - 50} more")
            if rec_uris and expand_recs:
                st.caption(f"+ {len(rec_uris)} recommendation(s) will be added")

        # Action buttons
        btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 2])

        with btn_col1:
            if st.button("Deploy This One", key=f"deploy_{pid}", use_container_width=True, type="primary"):
                if not user_id:
                    st.error("Could not determine Spotify user ID.")
                else:
                    # Reload fresh staged data before deploy
                    fresh = staging.load(pid)
                    if fresh:
                        with st.spinner("Deploying..."):
                            success, result = _deploy_one(fresh)
                        if success:
                            st.success(f"Deployed! [Open in Spotify]({result})")
                        else:
                            st.error(f"Deploy failed: {result}")
                    else:
                        st.error("Playlist not found in staging.")

        with btn_col2:
            # Remove button with confirmation
            if st.session_state["remove_confirm"] == pid:
                confirm_col1, confirm_col2 = st.columns(2)
                with confirm_col1:
                    if st.button("Confirm Remove", key=f"confirm_remove_{pid}", use_container_width=True):
                        try:
                            staging.delete(pid)
                        except Exception:
                            pass
                        st.session_state["remove_confirm"] = None
                        st.rerun()
                with confirm_col2:
                    if st.button("Cancel", key=f"cancel_remove_{pid}", use_container_width=True):
                        st.session_state["remove_confirm"] = None
                        st.rerun()
            else:
                if st.button("Remove", key=f"remove_{pid}", use_container_width=True):
                    st.session_state["remove_confirm"] = pid
                    st.rerun()

    st.write("")
