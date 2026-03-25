"""
pages/1_Connect.py — Spotify OAuth login page.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort — Connect",
    page_icon="🎧",
    layout="centered",
)

SCOPE = (
    "user-library-read user-top-read user-follow-read "
    "playlist-read-private playlist-read-collaborative "
    "playlist-modify-private playlist-modify-public"
)

SCOPE_DESCRIPTIONS = {
    "user-library-read":               "Read your liked songs",
    "user-top-read":                   "Read your top tracks and artists",
    "user-follow-read":                "Read artists you follow",
    "playlist-read-private":           "Read your private playlists",
    "playlist-read-collaborative":     "Read collaborative playlists you're in",
    "playlist-modify-private":         "Create private playlists in your account",
    "playlist-modify-public":          "Create public playlists in your account",
}


def get_sp():
    """Create and return a SpotifyOAuth manager and Spotify client."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        import config as cfg

        auth_manager = SpotifyOAuth(
            client_id=cfg.SPOTIFY_CLIENT_ID,
            client_secret=cfg.SPOTIFY_CLIENT_SECRET,
            redirect_uri=cfg.SPOTIFY_REDIRECT_URI,
            scope=SCOPE,
            cache_path=".vibesort_cache",
            open_browser=True,
        )
        return spotipy.Spotify(auth_manager=auth_manager), auth_manager
    except Exception as e:
        return None, None


# ── Page ─────────────────────────────────────────────────────────────────────

st.title("Vibesort")
st.caption("Your library, sorted by feeling.")

st.divider()

# Check if already authenticated
if st.session_state.get("spotify_token"):
    sp = st.session_state.get("sp")
    me = st.session_state.get("me", {})
    name = me.get("display_name") or me.get("id", "Spotify User")
    img_url = (me.get("images") or [{}])[0].get("url", "")

    col1, col2 = st.columns([1, 4])
    with col1:
        if img_url:
            st.image(img_url, width=64)
    with col2:
        st.success(f"Connected as **{name}**")

    st.write("")
    if st.button("Continue to Library Scan", type="primary", use_container_width=True):
        st.switch_page("pages/2_Scan.py")

    st.write("")
    if st.button("Disconnect", use_container_width=True):
        for key in ["spotify_token", "sp", "me", "vibesort"]:
            st.session_state.pop(key, None)
        st.rerun()

else:
    # Check for credentials
    try:
        import config as cfg
        has_creds = bool(cfg.SPOTIFY_CLIENT_ID and cfg.SPOTIFY_CLIENT_SECRET)
    except Exception:
        has_creds = False

    if not has_creds:
        st.error("Spotify credentials not found.")
        st.markdown(
            "**To get started:**\n\n"
            "1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)\n"
            "2. Create an app (any name)\n"
            "3. Add `http://localhost:8501` as a Redirect URI\n"
            "4. Copy your Client ID and Secret into `.env`\n"
            "5. Restart Vibesort"
        )
    else:
        st.subheader("Connect to Spotify")
        st.write("Vibesort needs access to your Spotify account to analyze your library and create playlists.")

        st.write("**Permissions requested:**")
        for scope, desc in SCOPE_DESCRIPTIONS.items():
            st.markdown(f"- {desc}")

        st.write("")

        # Handle OAuth callback code in URL params
        params = st.query_params
        code = params.get("code", None)

        if code:
            # Exchange code for token
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyOAuth
                import config as cfg

                auth_manager = SpotifyOAuth(
                    client_id=cfg.SPOTIFY_CLIENT_ID,
                    client_secret=cfg.SPOTIFY_CLIENT_SECRET,
                    redirect_uri=cfg.SPOTIFY_REDIRECT_URI,
                    scope=SCOPE,
                    cache_path=".vibesort_cache",
                    open_browser=False,
                )
                token_info = auth_manager.get_access_token(code)
                sp = spotipy.Spotify(auth_manager=auth_manager)
                me = sp.current_user()

                st.session_state["spotify_token"] = token_info
                st.session_state["sp"] = sp
                st.session_state["me"] = me

                # Clear code from URL
                st.query_params.clear()
                st.rerun()

            except Exception as e:
                st.error(f"Authentication failed: {e}")
                st.info("Please try connecting again.")

        else:
            # Show connect button
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyOAuth
                import config as cfg

                auth_manager = SpotifyOAuth(
                    client_id=cfg.SPOTIFY_CLIENT_ID,
                    client_secret=cfg.SPOTIFY_CLIENT_SECRET,
                    redirect_uri=cfg.SPOTIFY_REDIRECT_URI,
                    scope=SCOPE,
                    cache_path=".vibesort_cache",
                    open_browser=True,
                )

                # Check if there is a cached token
                cached_token = auth_manager.get_cached_token()
                if cached_token and not auth_manager.is_token_expired(cached_token):
                    sp = spotipy.Spotify(auth_manager=auth_manager)
                    me = sp.current_user()
                    st.session_state["spotify_token"] = cached_token
                    st.session_state["sp"] = sp
                    st.session_state["me"] = me
                    st.rerun()
                else:
                    auth_url = auth_manager.get_authorize_url()
                    st.link_button(
                        "Connect to Spotify",
                        auth_url,
                        use_container_width=True,
                        type="primary",
                    )
                    st.caption(
                        "You'll be redirected to Spotify to authorize access, "
                        "then brought back here automatically."
                    )

            except Exception as e:
                st.error(f"Could not initialize Spotify auth: {e}")
