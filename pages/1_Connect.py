"""
pages/1_Connect.py — Spotify OAuth login.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort",
    page_icon="🎧",
    layout="centered",
)

from core.theme import inject
inject()

SCOPE = (
    "user-library-read user-top-read user-follow-read "
    "playlist-read-private playlist-read-collaborative "
    "playlist-modify-private playlist-modify-public"
)

REDIRECT_URI = "https://papakoftes.github.io/VibeSort/callback.html"

PLACEHOLDER_VALUES = {
    "your_client_id_here", "your_id_here", "", "your_client_id",
    "paste_here", "paste_your_client_id_here",
}


def _creds_ok(client_id: str, client_secret: str) -> bool:
    return (
        bool(client_id)
        and bool(client_secret)
        and client_id.strip().lower() not in PLACEHOLDER_VALUES
        and client_secret.strip().lower() not in PLACEHOLDER_VALUES
        and len(client_id.strip()) > 10
        and len(client_secret.strip()) > 10
    )


def _get_auth_manager():
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        import config as cfg
        return SpotifyOAuth(
            client_id=cfg.SPOTIFY_CLIENT_ID,
            client_secret=cfg.SPOTIFY_CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=".vibesort_cache",
            open_browser=False,
        )
    except Exception:
        return None


# ── Already connected ─────────────────────────────────────────────────────────

if st.session_state.get("spotify_token"):
    me   = st.session_state.get("me", {})
    name = me.get("display_name") or me.get("id", "Spotify User")
    img  = (me.get("images") or [{}])[0].get("url", "")

    st.title("Vibesort")
    st.divider()

    c1, c2 = st.columns([1, 5])
    with c1:
        if img:
            st.image(img, width=56)
    with c2:
        st.success(f"Connected as **{name}**")

    st.write("")
    if st.button("Scan Library →", type="primary", use_container_width=True):
        st.switch_page("pages/2_Scan.py")

    if st.button("Disconnect", use_container_width=True):
        for k in ["spotify_token", "sp", "me", "vibesort"]:
            st.session_state.pop(k, None)
        try:
            if os.path.exists(".vibesort_cache"):
                os.remove(".vibesort_cache")
        except Exception:
            pass
        st.rerun()

    st.stop()


# ── Handle OAuth callback code in URL params ──────────────────────────────────

code = st.query_params.get("code")
if code:
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        import config as cfg

        auth_manager = SpotifyOAuth(
            client_id=cfg.SPOTIFY_CLIENT_ID,
            client_secret=cfg.SPOTIFY_CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=".vibesort_cache",
            open_browser=False,
        )
        token_info = auth_manager.get_access_token(code)
        sp = spotipy.Spotify(auth_manager=auth_manager)
        me = sp.current_user()

        st.session_state["spotify_token"] = token_info
        st.session_state["sp"]            = sp
        st.session_state["me"]            = me
        st.query_params.clear()
        st.rerun()

    except Exception as e:
        st.error(f"Auth failed: {e}")
        st.info("Try connecting again.")
    st.stop()


# ── Not connected — check for credentials ────────────────────────────────────

try:
    import config as cfg
    client_id     = (cfg.SPOTIFY_CLIENT_ID     or "").strip()
    client_secret = (cfg.SPOTIFY_CLIENT_SECRET or "").strip()
    has_creds     = _creds_ok(client_id, client_secret)
except Exception:
    has_creds = False
    client_id = client_secret = ""


st.title("Vibesort")
st.caption("Your library, sorted by feeling.")
st.divider()


if not has_creds:
    # ── Setup instructions ────────────────────────────────────────────────────
    st.subheader("Setup — 3 steps, 5 minutes")
    st.write("")

    st.markdown("**① Create a free Spotify developer app**")
    st.link_button(
        "Open Spotify Developer Dashboard →",
        "https://developer.spotify.com/dashboard",
        use_container_width=True,
    )
    st.write("")

    st.markdown(
        "In the dashboard: **Create app** → any name → under **Settings**, "
        "add this exact redirect URI:"
    )
    st.code("https://papakoftes.github.io/VibeSort/callback.html", language=None)
    st.caption("Copy that exactly. Then copy your **Client ID** and **Client Secret**.")
    st.write("")

    st.markdown("**② Paste credentials into `.env`**")
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    st.code(f"# open this file:\n{env_path}", language=None)
    st.markdown(
        "Fill in:\n"
        "```\n"
        "SPOTIFY_CLIENT_ID=your_id_here\n"
        "SPOTIFY_CLIENT_SECRET=your_secret_here\n"
        "```"
    )
    st.write("")

    st.markdown("**③ Restart Vibesort**")
    st.caption("Run `python launch.py` again. This page will update automatically.")

    if client_id and client_id.lower() in PLACEHOLDER_VALUES:
        st.warning("`.env` still has placeholder values — replace them with your real credentials.")
    elif client_id and not has_creds:
        st.warning("Credentials look incomplete. Make sure both Client ID and Secret are filled in.")

else:
    # ── Show connect button ───────────────────────────────────────────────────

    # Check for cached valid token first
    auth_manager = _get_auth_manager()
    if auth_manager:
        try:
            cached = auth_manager.get_cached_token()
            if cached and not auth_manager.is_token_expired(cached):
                import spotipy
                sp = spotipy.Spotify(auth_manager=auth_manager)
                me = sp.current_user()
                st.session_state["spotify_token"] = cached
                st.session_state["sp"]            = sp
                st.session_state["me"]            = me
                st.rerun()
        except Exception:
            pass

    st.subheader("Connect to Spotify")
    st.write(
        "Vibesort will read your liked songs, top tracks, and followed artists "
        "to build playlists. It will only write playlists you explicitly deploy."
    )
    st.write("")

    if auth_manager:
        auth_url = auth_manager.get_authorize_url()
        st.link_button(
            "Connect to Spotify →",
            auth_url,
            use_container_width=True,
            type="primary",
        )
        st.caption(
            "You'll be redirected to Spotify, then automatically returned here. "
            "Vibesort never stores your password."
        )
    else:
        st.error("Could not initialize Spotify auth — check your `.env` credentials.")
