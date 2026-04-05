"""
pages/1_Connect.py — Spotify OAuth login.

Two auth modes:
  PKCE mode  — VIBESORT_CLIENT_ID is set in .env (or config.py).
               End users click Connect and never touch Spotify's dashboard.
  OAuth mode — User provides their own SPOTIFY_CLIENT_ID + SECRET in .env.
               Fallback / power-user option.
"""
import os, sys, time, json
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
PLACEHOLDERS = {"your_client_id_here", "your_id_here", "", "paste_here",
                "your_client_id", "paste_your_client_id_here"}


def _creds_ok(cid, secret):
    return (bool(cid) and bool(secret)
            and cid.strip().lower()     not in PLACEHOLDERS
            and secret.strip().lower()  not in PLACEHOLDERS
            and len(cid.strip())    > 10
            and len(secret.strip()) > 10)


def _make_oauth(cid, secret):
    from spotipy.oauth2 import SpotifyOAuth
    return SpotifyOAuth(
        client_id=cid, client_secret=secret,
        redirect_uri=REDIRECT_URI, scope=SCOPE,
        cache_path=".vibesort_cache", open_browser=False,
    )


# ── Load config ───────────────────────────────────────────────────────────────
try:
    import config as cfg
    SHARED_ID  = (cfg.VIBESORT_CLIENT_ID    or "").strip()
    USER_ID    = (cfg.SPOTIFY_CLIENT_ID     or "").strip()
    USER_SEC   = (cfg.SPOTIFY_CLIENT_SECRET or "").strip()
except Exception:
    SHARED_ID = USER_ID = USER_SEC = ""

USE_PKCE  = bool(SHARED_ID)
USE_OAUTH = _creds_ok(USER_ID, USER_SEC)
CLIENT_ID = SHARED_ID or USER_ID   # whichever is active


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
    if st.button("Scan Library", type="primary", use_container_width=True):
        st.switch_page("pages/2_Scan.py")
    if st.button("Disconnect", use_container_width=True):
        for k in ["spotify_token", "sp", "me", "vibesort", "pkce_token"]:
            st.session_state.pop(k, None)
        if USE_PKCE:
            from core.pkce import clear_token
            clear_token()
        for f in [".vibesort_pkce_state"]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except OSError:
                pass
        st.rerun()
    st.stop()


# ── Handle OAuth callback ?code= ──────────────────────────────────────────────
# Code arrives either directly in query params (user bookmarked /1_Connect)
# or forwarded via session_state from app.py (normal flow via root redirect).
code = (
    st.query_params.get("code")
    or st.session_state.pop("_pending_code", None)
)
if code:
    with st.spinner("Connecting..."):
        try:
            import spotipy

            if USE_PKCE:
                from core.pkce import exchange_code, make_spotify, save_token
                returned_state = (
                    st.query_params.get("state")
                    or st.session_state.pop("_pending_state", "")
                )
                token = exchange_code(code, SHARED_ID, REDIRECT_URI, returned_state)
                sp, token = make_spotify(token, SHARED_ID)
                save_token(token)
                st.session_state["pkce_token"] = token
                st.session_state.pop("pkce_auth_url", None)  # force fresh URL next time

            else:
                from spotipy.oauth2 import SpotifyOAuth
                auth = _make_oauth(USER_ID, USER_SEC)
                token = auth.get_access_token(code)
                sp = spotipy.Spotify(auth_manager=auth)

            me = sp.current_user()
            st.session_state["spotify_token"] = token
            st.session_state["sp"]            = sp
            st.session_state["me"]            = me
            st.query_params.clear()
            st.rerun()

        except Exception as e:
            st.error(f"Auth failed: {e}")
            st.info("Try connecting again.")
    st.stop()


# ── Check for cached/valid existing token ─────────────────────────────────────
if USE_PKCE:
    from core.pkce import make_spotify, refresh_access_token, load_token, save_token
    # Session first, then disk cache (survives restarts)
    cached = st.session_state.get("pkce_token") or load_token()
    if cached:
        try:
            import spotipy
            sp, refreshed = make_spotify(cached, SHARED_ID)
            if refreshed is not cached:
                save_token(refreshed)
                st.session_state["pkce_token"] = refreshed
            me = sp.current_user()
            st.session_state["spotify_token"] = refreshed
            st.session_state["sp"]            = sp
            st.session_state["me"]            = me
            st.rerun()
        except Exception:
            pass

elif USE_OAUTH:
    try:
        auth = _make_oauth(USER_ID, USER_SEC)
        cached = auth.get_cached_token()
        if cached and not auth.is_token_expired(cached):
            import spotipy
            sp = spotipy.Spotify(auth_manager=auth)
            me = sp.current_user()
            st.session_state["spotify_token"] = cached
            st.session_state["sp"]            = sp
            st.session_state["me"]            = me
            st.rerun()
    except Exception:
        pass


# ── Connect page UI ───────────────────────────────────────────────────────────
st.title("Vibesort")
st.caption("Your library, sorted by feeling.")
st.divider()

if USE_PKCE or USE_OAUTH:
    # ── Auth is configured — show Connect button ──────────────────────────────
    st.subheader("Connect to Spotify")
    st.write(
        "Vibesort reads your liked songs, top tracks, and followed artists. "
        "It only writes playlists you explicitly deploy."
    )
    st.write("")

    if USE_PKCE:
        from core.pkce import generate_auth_url
        # Cache auth URL in session_state — generate_auth_url() writes the PKCE
        # verifier to disk. If we call it on every re-render we overwrite the
        # state file between click and callback, breaking the code exchange.
        if "pkce_auth_url" not in st.session_state:
            auth_url = generate_auth_url(SHARED_ID, REDIRECT_URI, SCOPE)
            st.session_state["pkce_auth_url"] = auth_url
        else:
            auth_url = st.session_state["pkce_auth_url"]
    else:
        auth_url = _make_oauth(USER_ID, USER_SEC).get_authorize_url()

    # target="_self" so auth happens in the same tab/session —
    # a new tab would create a separate Streamlit session and the token
    # would never reach this page.
    st.markdown(
        f"""
        <a href="{auth_url}" target="_self" style="
            display: block;
            width: 100%;
            padding: 0.65rem 1rem;
            text-align: center;
            background: #c0006a;
            color: #ffffff;
            border-radius: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 1rem;
            font-weight: 600;
            text-decoration: none;
            letter-spacing: 0.04em;
            border: 1px solid #8b0000;
            box-shadow: 0 0 12px #c0006a44;
            transition: box-shadow 0.2s;
        ">Connect to Spotify</a>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "You'll be taken to Spotify to authorize, then returned here automatically."
    )

else:
    # ── No credentials at all — show setup instructions ───────────────────────
    st.subheader("Setup — 3 steps, 5 minutes")
    st.write("")

    st.markdown("**1. Create a free Spotify developer app**")
    st.link_button(
        "Open Spotify Developer Dashboard",
        "https://developer.spotify.com/dashboard",
        use_container_width=True,
    )
    st.write("")

    st.markdown(
        "**2.** In your new app → **Settings** → add this Redirect URI exactly:"
    )
    st.code("https://papakoftes.github.io/VibeSort/callback.html", language=None)
    st.write("")

    st.markdown("**3.** Copy your **Client ID** and **Client Secret** into `.env`:")
    st.code(
        "SPOTIFY_CLIENT_ID=paste_here\nSPOTIFY_CLIENT_SECRET=paste_here",
        language="bash",
    )
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
    )
    st.caption(f"File location: `{env_path}`")
    st.write("")
    st.info("Save `.env` then restart Vibesort — this page will update automatically.")

st.divider()
with st.expander("Sharing with friends & going beyond the Spotify “test user” cap"):
    st.markdown(
        """
**Today (typical Spotify app in Development Mode)**  
You can add a small set of **test users** in the Spotify Developer Dashboard. Everyone else
will get blocked until they are on that list — fine for a closed beta.

**Unlimited listeners (production-style)**  
Spotify requires you to **submit the app for review** and move toward **production /
Extended Quota** on their terms. There is no legal shortcut around that for the official
Web API: if you want strangers to log in without being manually whitelisted, you need an
approved integration.

**Practical paths**
- **Friends run Vibesort locally** — each person uses their own machine (or their own
  Spotify app + `.env`) so your quota is not shared.
- **You host the Streamlit app** — still uses *your* Spotify client; scale only after
  Spotify approves broader access.
- **Last.fm / ListenBrainz / Genius** stay **per-user API keys or tokens in `.env`** for now;
  full “Sign in with Last.fm” style OAuth can be added later — Musixmatch is primarily
  API-key based for lyrics metadata.

Built-in sources (Deezer public search, lrclib, etc.) need no per-user login.
        """
    )
