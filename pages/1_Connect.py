"""
pages/1_Connect.py — Spotify OAuth login + optional service connections.

Two Spotify auth modes:
  PKCE mode  — VIBESORT_CLIENT_ID is set in .env (or config.py).
               End users click Connect and never touch Spotify's dashboard.
  OAuth mode — User provides their own SPOTIFY_CLIENT_ID + SECRET in .env.
               Fallback / power-user option.

Additional connections (configured here without editing .env):
  Last.fm    — Free API key; powers artist genre + track mood tags.
               Strongly recommended for best playlist quality.
  Own Spotify app — Bypass the shared 25-user Dev Mode quota by using your
               own Spotify Client ID (PKCE, no secret needed).
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
import config as _connect_cfg
REDIRECT_URI = _connect_cfg.SPOTIFY_REDIRECT_URI or "https://papakoftes.github.io/VibeSort/callback.html"
PLACEHOLDERS = {"your_client_id_here", "your_id_here", "", "paste_here",
                "your_client_id", "paste_your_client_id_here"}

_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def _update_env_key(key: str, value: str) -> bool:
    """Write or update a single key in the project's .env file."""
    try:
        lines: list[str] = []
        if os.path.exists(_ENV_PATH):
            with open(_ENV_PATH, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        new_lines: list[str] = []
        found = False
        for line in lines:
            if line.strip().startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{key}={value}\n")
        with open(_ENV_PATH, "w", encoding="utf-8") as fh:
            fh.writelines(new_lines)
        return True
    except Exception:
        return False


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


# ── Helpers: resolve active Last.fm credentials ───────────────────────────────

def _lf_app_creds() -> tuple[str, str]:
    """
    Return (api_key, api_secret) for the shared Vibesort Last.fm app.
    Falls back to per-user LASTFM_API_KEY if shared key not yet configured.
    """
    try:
        import config as _c
        shared_k = (getattr(_c, "VIBESORT_LASTFM_API_KEY",    "") or "").strip()
        shared_s = (getattr(_c, "VIBESORT_LASTFM_API_SECRET", "") or "").strip()
        if shared_k and shared_s:
            return shared_k, shared_s
        # Fallback: per-user key (if developer hasn't registered shared app yet)
        user_k = (getattr(_c, "LASTFM_API_KEY",    "") or "").strip()
        user_s = (getattr(_c, "LASTFM_API_SECRET", "") or "").strip()
        if user_k and user_s:
            return user_k, user_s
        if user_k:
            return user_k, ""
    except Exception:
        pass
    return "", ""


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

# ── Restore Last.fm session from disk on every cold start ─────────────────────
# session_state is ephemeral — after a restart the UI would show "not connected"
# even though the session file on disk is valid. Load it once here so the
# connect status and the scan pipeline see the same state.
if "lastfm_session" not in st.session_state:
    try:
        from core.lastfm import load_session as _lf_disk_load
        _disk_sess = _lf_disk_load()
        if _disk_sess and _disk_sess.get("key") and _disk_sess.get("name"):
            st.session_state["lastfm_session"] = _disk_sess
    except Exception:
        pass


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
        st.success(f"✅ Spotify — connected as **{name}**")
    st.write("")

    # ── Inline Last.fm status — shown right next to Spotify so users connect both
    _inline_lf_sess  = st.session_state.get("lastfm_session") or {}
    _inline_lf_user  = _inline_lf_sess.get("name", "")
    _lf_k_i, _lf_s_i = _lf_app_creds()

    if _inline_lf_user:
        st.success(f"✅ Last.fm — connected as **{_inline_lf_user}**")
    elif _lf_k_i:
        st.info(
            "**Connect Last.fm** for personalised mood tags and listening history — "
            "strongly recommended for best playlist quality."
        )
        from core.lastfm import generate_auth_url as _lf_inline_url
        _inline_lf_oauth = _lf_inline_url(_lf_k_i)
        st.markdown(
            f"""
            <a href="{_inline_lf_oauth}" target="_self" style="
                display: block;
                width: 100%;
                padding: 0.60rem 1rem;
                text-align: center;
                background: #d51007;
                color: #ffffff;
                border-radius: 8px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 1rem;
                font-weight: 600;
                text-decoration: none;
                letter-spacing: 0.04em;
                border: 1px solid #8b0000;
                box-shadow: 0 0 12px #d5100744;
            ">Connect Last.fm →</a>
            """,
            unsafe_allow_html=True,
        )
        st.caption("You'll be taken to Last.fm to authorise, then returned here automatically.")
        st.write("")

    if st.button("Scan Library", type="primary", use_container_width=True):
        st.switch_page("pages/2_Scan.py")
    if st.button("Disconnect Spotify", use_container_width=True):
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
    # NOTE: do NOT st.stop() here — page continues to render service connections below


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
if USE_PKCE and not st.session_state.get("spotify_token"):
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

elif USE_OAUTH and not st.session_state.get("spotify_token"):
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

if not st.session_state.get("spotify_token") and (USE_PKCE or USE_OAUTH):
    # ── Auth is configured — show Connect button (only when not yet connected) ─
    st.subheader("Connect to Spotify")
    st.write(
        "Vibesort reads your liked songs, top tracks, and followed artists. "
        "It only **creates** playlists you explicitly deploy — it never modifies or deletes anything in your library. "
        "All processing runs locally on your machine."
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
    st.info(
        "**App currently in Spotify Development Mode (25-user limit).**  \n"
        "If Spotify says you're not registered: use your own free Spotify developer app instead — "
        "takes about 5 minutes. [Open Spotify Dashboard →](https://developer.spotify.com/dashboard)  \n"
        "Create an app, add `https://papakoftes.github.io/VibeSort/callback.html` as Redirect URI, "
        "then paste your **Client ID** into Settings here or into `.env`."
    )

elif not st.session_state.get("spotify_token"):
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

# ── Last.fm connection ────────────────────────────────────────────────────────
st.subheader("Last.fm  ·  Mood & genre tags")
st.caption(
    "Strongly recommended. Crowd-sourced mood tags per artist and track — "
    "'sad', 'dark', 'chill', 'hype' — go straight into the scoring engine. "
    "Also unlocks your personal loved tracks and top artists for smarter playlists."
)

# ── Handle incoming web-auth token (from GitHub Pages callback) ───────────────
_pending_lf_token = st.session_state.pop("_pending_lastfm_token", None)
if _pending_lf_token:
    _lf_k, _lf_s = _lf_app_creds()
    if _lf_k and _lf_s:
        with st.spinner("Connecting to Last.fm..."):
            from core.lastfm import exchange_token as _lf_exchange, save_session as _lf_save
            _sess = _lf_exchange(_pending_lf_token, _lf_k, _lf_s)
        if _sess and _sess.get("key"):
            _lf_save(_sess)
            st.session_state["lastfm_session"] = _sess
            try:
                cfg.LASTFM_API_KEY = _lf_k
            except Exception:
                pass
            st.success(f"✅ Connected to Last.fm as **{_sess.get('name', '')}**")
            st.rerun()
        else:
            st.error("Last.fm connection failed — token may have expired. Try again.")
    else:
        # No shared key configured yet — fall through to manual key section
        pass

# ── Show connection status or connect button ─────────────────────────────────
_lf_session = st.session_state.get("lastfm_session") or {}
_lf_username = _lf_session.get("name", "")
_lf_key_only = (                       # API key available but no user auth
    st.session_state.get("lastfm_api_key_runtime")
    or getattr(cfg, "LASTFM_API_KEY", "").strip()
)
_lf_k, _lf_s = _lf_app_creds()

if _lf_username:
    # ── Fully authenticated ────────────────────────────────────────────────
    st.success(f"✅ Connected as **{_lf_username}** on Last.fm")
    st.caption("Your loved tracks and listening history will be used to personalise playlists.")
    if st.button("Disconnect Last.fm", key="lf_disconnect"):
        from core.lastfm import clear_session as _lf_clear
        _lf_clear()
        st.session_state.pop("lastfm_session", None)
        st.session_state.pop("lastfm_api_key_runtime", None)
        st.rerun()

elif _lf_k:
    # ── Shared key available — show OAuth button ───────────────────────────
    from core.lastfm import generate_auth_url as _lf_auth_url
    _lf_oauth_url = _lf_auth_url(_lf_k)
    st.markdown(
        f"""
        <a href="{_lf_oauth_url}" target="_self" style="
            display: block;
            width: 100%;
            padding: 0.60rem 1rem;
            text-align: center;
            background: #d51007;
            color: #ffffff;
            border-radius: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 1rem;
            font-weight: 600;
            text-decoration: none;
            letter-spacing: 0.04em;
            border: 1px solid #8b0000;
            box-shadow: 0 0 12px #d5100744;
        ">Connect with Last.fm</a>
        """,
        unsafe_allow_html=True,
    )
    st.caption("You'll be taken to Last.fm to authorise, then returned here automatically.")

    if _lf_key_only and not _lf_username:
        st.caption(
            f"_(API key active, not logged in — click above to get personal recommendations)_"
        )

else:
    # ── No shared key — developer hasn't registered the Vibesort Last.fm app yet ──
    st.info(
        "Last.fm connection requires the developer to register a shared Vibesort app. "
        "See the setup instructions below, or enter your own API key as a fallback."
    )
    with st.expander("Developer setup (one-time): register the shared Vibesort Last.fm app"):
        st.markdown(
            """
1. Go to **[last.fm/api/account/create](https://www.last.fm/api/account/create)** and log in.
2. Fill in: Application name = `Vibesort`, Homepage = `https://github.com/PapaKoftes/VibeSort`.
3. Copy the **API Key** and **Shared Secret**.
4. Add to `config.py` (or `.env`):
```
VIBESORT_LASTFM_API_KEY=your_api_key_here
VIBESORT_LASTFM_API_SECRET=your_shared_secret_here
```
5. Restart the app — the "Connect with Last.fm" button will appear for all users.
            """
        )
    # Fallback: manual key input (for users who have their own key)
    _lf_input = st.text_input(
        "Or paste your own Last.fm API key (personal fallback)",
        type="password",
        placeholder="32-character API key",
        key="lf_key_input",
    )
    if st.button("Save API key", key="lf_save"):
        _k = (_lf_input or "").strip()
        if len(_k) < 16:
            st.error("Key looks too short — check it and try again.")
        else:
            _update_env_key("LASTFM_API_KEY", _k)
            try:
                cfg.LASTFM_API_KEY = _k
            except Exception:
                pass
            st.session_state["lastfm_api_key_runtime"] = _k
            st.success("✅ API key saved. Re-scan to use it.")
            st.rerun()


# ── Last.fm username (no OAuth path) ─────────────────────────────────────────
_lf_username_env = (
    st.session_state.get("lastfm_username_runtime")
    or getattr(cfg, "LASTFM_USERNAME", "").strip()
)
_show_lf_username = not _lf_username or True   # always show as supplement
with st.expander(
    ("✏️ Edit Last.fm username" if _lf_username else "Set Last.fm username (no login needed)"),
    expanded=False,
):
    st.caption(
        "If you don't want to authenticate via OAuth, just enter your public Last.fm username. "
        "Vibesort will fetch your top artists and tags using the public API — no password or session needed."
    )
    _lf_uname_cur = _lf_username or _lf_username_env or ""
    _lf_uname_in = st.text_input(
        "Last.fm username",
        value=_lf_uname_cur,
        placeholder="e.g. rj",
        key="lf_username_input",
    )
    if st.button("Save username", key="lf_uname_save"):
        _un = (_lf_uname_in or "").strip()
        if not _un:
            st.error("Please enter a username.")
        else:
            _update_env_key("LASTFM_USERNAME", _un)
            try:
                cfg.LASTFM_USERNAME = _un
            except Exception:
                pass
            st.session_state["lastfm_username_runtime"] = _un
            st.success(f"✅ Last.fm username saved as **{_un}**. Re-scan to use it.")
            st.rerun()
    if _lf_uname_cur and st.button("Clear username", key="lf_uname_clear"):
        _update_env_key("LASTFM_USERNAME", "")
        try:
            cfg.LASTFM_USERNAME = ""
        except Exception:
            pass
        st.session_state.pop("lastfm_username_runtime", None)
        st.rerun()

st.divider()

# ── ListenBrainz connection ───────────────────────────────────────────────────
st.subheader("ListenBrainz  ·  Listening history")
st.caption(
    "Optional but powerful. Your personal play counts are used to boost frequently-listened "
    "tracks to the top of playlists. Free account at listenbrainz.org — takes 30 seconds."
)

_lb_token_saved = (
    st.session_state.get("listenbrainz_token_runtime")
    or getattr(cfg, "LISTENBRAINZ_TOKEN", "").strip()
)
_lb_user_saved = (
    st.session_state.get("listenbrainz_username_runtime")
    or getattr(cfg, "LISTENBRAINZ_USERNAME", "").strip()
)

if _lb_token_saved and _lb_user_saved:
    st.success(f"✅ Connected as **{_lb_user_saved}** on ListenBrainz")
    st.caption("Your listening history will be used to prioritise frequently-played tracks.")
    if st.button("Disconnect ListenBrainz", key="lb_disconnect"):
        _update_env_key("LISTENBRAINZ_TOKEN", "")
        _update_env_key("LISTENBRAINZ_USERNAME", "")
        try:
            cfg.LISTENBRAINZ_TOKEN    = ""
            cfg.LISTENBRAINZ_USERNAME = ""
        except Exception:
            pass
        st.session_state.pop("listenbrainz_token_runtime", None)
        st.session_state.pop("listenbrainz_username_runtime", None)
        st.rerun()
else:
    with st.form("lb_connect_form"):
        st.markdown(
            "1. Create a free account at [listenbrainz.org](https://listenbrainz.org/)\n"
            "2. Go to your **Profile → API Token** — copy the token\n"
            "3. Paste it below with your username"
        )
        _lb_token_input = st.text_input(
            "ListenBrainz API token",
            type="password",
            placeholder="Paste your token here",
            key="lb_token_input",
        )
        _lb_user_input = st.text_input(
            "ListenBrainz username",
            placeholder="Your ListenBrainz username",
            key="lb_user_input",
        )
        _lb_submit = st.form_submit_button("Connect ListenBrainz", use_container_width=True)
        if _lb_submit:
            _tok = (_lb_token_input or "").strip()
            _usr = (_lb_user_input or "").strip()
            if len(_tok) < 10:
                st.error("Token looks too short — check it and try again.")
            elif not _usr:
                st.error("Username is required.")
            else:
                _update_env_key("LISTENBRAINZ_TOKEN", _tok)
                _update_env_key("LISTENBRAINZ_USERNAME", _usr)
                try:
                    cfg.LISTENBRAINZ_TOKEN    = _tok
                    cfg.LISTENBRAINZ_USERNAME = _usr
                except Exception:
                    pass
                st.session_state["listenbrainz_token_runtime"]    = _tok
                st.session_state["listenbrainz_username_runtime"] = _usr
                st.success(f"✅ Connected as **{_usr}**. Re-scan to use your listening history.")
                st.rerun()

st.divider()

# ── Maloja connection ─────────────────────────────────────────────────────────
st.subheader("Maloja  ·  Self-hosted scrobble server")
st.caption(
    "Run your own Last.fm-compatible scrobble server. "
    "Play counts from Maloja are used to boost frequently-listened tracks, "
    "same as ListenBrainz. [maloja.krateng.ch](https://maloja.krateng.ch)"
)

_maloja_url_saved = (
    st.session_state.get("maloja_url_runtime")
    or getattr(cfg, "MALOJA_URL", "").strip()
)
_maloja_token_saved = (
    st.session_state.get("maloja_token_runtime")
    or getattr(cfg, "MALOJA_TOKEN", "").strip()
)

if _maloja_url_saved and _maloja_token_saved:
    st.success(f"✅ Maloja connected — {_maloja_url_saved}")
    _c1_m, _c2_m = st.columns([3, 1])
    with _c2_m:
        if st.button("Disconnect Maloja", key="maloja_disconnect"):
            _update_env_key("MALOJA_URL", "")
            _update_env_key("MALOJA_TOKEN", "")
            try:
                cfg.MALOJA_URL   = ""
                cfg.MALOJA_TOKEN = ""
            except Exception:
                pass
            st.session_state.pop("maloja_url_runtime", None)
            st.session_state.pop("maloja_token_runtime", None)
            st.rerun()
else:
    with st.form("maloja_form"):
        st.markdown(
            "1. Run Maloja and open its admin panel\n"
            "2. Go to **Settings → API** and copy the API token\n"
            "3. Paste your server URL and token below"
        )
        _m_url = st.text_input(
            "Maloja server URL",
            placeholder="http://localhost:42010",
            key="maloja_url_input",
        )
        _m_tok = st.text_input(
            "Maloja API token",
            type="password",
            placeholder="Your Maloja API token",
            key="maloja_token_input",
        )
        _m_submit = st.form_submit_button("Connect Maloja", use_container_width=True)
        if _m_submit:
            _murl = (_m_url or "").strip().rstrip("/")
            _mtok = (_m_tok or "").strip()
            if not _murl or not _mtok:
                st.error("Both URL and token are required.")
            else:
                try:
                    from core import maloja as _maloja_mod
                    _info = _maloja_mod.ping(_murl, _mtok)
                    if _info:
                        _update_env_key("MALOJA_URL",   _murl)
                        _update_env_key("MALOJA_TOKEN", _mtok)
                        try:
                            cfg.MALOJA_URL   = _murl
                            cfg.MALOJA_TOKEN = _mtok
                        except Exception:
                            pass
                        st.session_state["maloja_url_runtime"]   = _murl
                        st.session_state["maloja_token_runtime"] = _mtok
                        st.success(
                            f"✅ Connected to **{_info.get('name', 'Maloja')}** "
                            f"v{_info.get('version', '?')}. Re-scan to use your history."
                        )
                        st.rerun()
                    else:
                        st.error(
                            "Could not reach the Maloja server. "
                            "Check the URL and token, and make sure the server is running."
                        )
                except Exception as _me:
                    st.error(f"Connection error: {_me}")

st.divider()

# ── Navidrome / Jellyfin connection ───────────────────────────────────────────
st.subheader("Navidrome / Jellyfin  ·  Self-hosted music server")
st.caption(
    "Uses the OpenSubsonic API. Starred tracks get a boost in playlist scoring. "
    "Local file genre tags fill gaps that Spotify doesn't cover. "
    "Works with Navidrome, Jellyfin, Airsonic-Advanced, and any OpenSubsonic server."
)

_nd_url_saved   = st.session_state.get("navidrome_url_runtime")   or getattr(cfg, "NAVIDROME_URL",  "").strip()
_nd_user_saved  = st.session_state.get("navidrome_user_runtime")  or getattr(cfg, "NAVIDROME_USER", "").strip()
_nd_pass_saved  = st.session_state.get("navidrome_pass_runtime")  or getattr(cfg, "NAVIDROME_PASS", "").strip()

if _nd_url_saved and _nd_user_saved and _nd_pass_saved:
    st.success(f"✅ Navidrome connected — {_nd_url_saved} (as **{_nd_user_saved}**)")
    if st.button("Disconnect Navidrome", key="nd_disconnect"):
        for _k in ("NAVIDROME_URL", "NAVIDROME_USER", "NAVIDROME_PASS"):
            _update_env_key(_k, "")
        try:
            cfg.NAVIDROME_URL  = ""
            cfg.NAVIDROME_USER = ""
            cfg.NAVIDROME_PASS = ""
        except Exception:
            pass
        for _sk in ("navidrome_url_runtime", "navidrome_user_runtime", "navidrome_pass_runtime"):
            st.session_state.pop(_sk, None)
        st.rerun()
else:
    with st.form("navidrome_form"):
        st.markdown(
            "Enter your Navidrome (or Jellyfin) server details below.\n"
            "Credentials are stored locally in `.env` — never sent anywhere else."
        )
        _nd_url_in  = st.text_input("Server URL",  placeholder="http://localhost:4533", key="nd_url_in")
        _nd_user_in = st.text_input("Username",    placeholder="admin",                 key="nd_user_in")
        _nd_pass_in = st.text_input("Password",    type="password",                     key="nd_pass_in")
        _nd_submit  = st.form_submit_button("Connect Navidrome", use_container_width=True)
        if _nd_submit:
            _nurl = (_nd_url_in  or "").strip().rstrip("/")
            _nusr = (_nd_user_in or "").strip()
            _npas = (_nd_pass_in or "").strip()
            if not _nurl or not _nusr or not _npas:
                st.error("Server URL, username, and password are all required.")
            else:
                try:
                    from core import navidrome as _nd_mod
                    _ninfo = _nd_mod.ping(_nurl, _nusr, _npas)
                    if _ninfo:
                        for _k, _v in [("NAVIDROME_URL", _nurl), ("NAVIDROME_USER", _nusr), ("NAVIDROME_PASS", _npas)]:
                            _update_env_key(_k, _v)
                        try:
                            cfg.NAVIDROME_URL  = _nurl
                            cfg.NAVIDROME_USER = _nusr
                            cfg.NAVIDROME_PASS = _npas
                        except Exception:
                            pass
                        st.session_state["navidrome_url_runtime"]  = _nurl
                        st.session_state["navidrome_user_runtime"] = _nusr
                        st.session_state["navidrome_pass_runtime"] = _npas
                        st.success(
                            f"✅ Connected to **{_ninfo.get('server', 'Navidrome')}** "
                            f"v{_ninfo.get('version', '?')}. Re-scan to use starred tracks."
                        )
                        st.rerun()
                    else:
                        st.error("Could not reach the server. Check the URL and credentials.")
                except Exception as _nde:
                    st.error(f"Connection error: {_nde}")

st.divider()

# ── Plex connection ───────────────────────────────────────────────────────────
st.subheader("Plex  ·  Plex Media Server")
st.caption(
    "Rated and recently-played tracks get a priority boost. "
    "Local file genre tags fill enrichment gaps. "
    "Requires your Plex token — find it in Settings → Troubleshooting on plex.tv."
)

_plex_url_saved   = st.session_state.get("plex_url_runtime")   or getattr(cfg, "PLEX_URL",   "").strip()
_plex_token_saved = st.session_state.get("plex_token_runtime") or getattr(cfg, "PLEX_TOKEN", "").strip()

if _plex_url_saved and _plex_token_saved:
    st.success(f"✅ Plex connected — {_plex_url_saved}")
    if st.button("Disconnect Plex", key="plex_disconnect"):
        _update_env_key("PLEX_URL",   "")
        _update_env_key("PLEX_TOKEN", "")
        try:
            cfg.PLEX_URL   = ""
            cfg.PLEX_TOKEN = ""
        except Exception:
            pass
        st.session_state.pop("plex_url_runtime",   None)
        st.session_state.pop("plex_token_runtime", None)
        st.rerun()
else:
    with st.form("plex_form"):
        st.markdown(
            "1. Find your Plex token: **plex.tv** → Account → **Authorized Devices** → any device URL → `X-Plex-Token=...`\n"
            "2. Your server URL is usually `http://localhost:32400` for local servers."
        )
        _px_url_in = st.text_input("Plex server URL",   placeholder="http://localhost:32400", key="px_url_in")
        _px_tok_in = st.text_input("Plex token",        type="password",                      key="px_tok_in")
        _px_submit = st.form_submit_button("Connect Plex", use_container_width=True)
        if _px_submit:
            _pxurl = (_px_url_in or "").strip().rstrip("/")
            _pxtok = (_px_tok_in or "").strip()
            if not _pxurl or not _pxtok:
                st.error("Both server URL and token are required.")
            else:
                try:
                    from core import plex as _plex_mod
                    _pxinfo = _plex_mod.ping(_pxurl, _pxtok)
                    if _pxinfo:
                        _update_env_key("PLEX_URL",   _pxurl)
                        _update_env_key("PLEX_TOKEN", _pxtok)
                        try:
                            cfg.PLEX_URL   = _pxurl
                            cfg.PLEX_TOKEN = _pxtok
                        except Exception:
                            pass
                        st.session_state["plex_url_runtime"]   = _pxurl
                        st.session_state["plex_token_runtime"] = _pxtok
                        st.success(
                            f"✅ Connected to **{_pxinfo.get('server', 'Plex')}** "
                            f"v{_pxinfo.get('version', '?')}. Re-scan to use your library."
                        )
                        st.rerun()
                    else:
                        st.error("Could not reach Plex. Check the URL and token.")
                except Exception as _pxe:
                    st.error(f"Connection error: {_pxe}")

st.divider()

# ── Apple Music connection ────────────────────────────────────────────────────
st.subheader("Apple Music  ·  Library XML import")
st.caption(
    "Import your Apple Music loved tracks, ratings, and play counts. "
    "No API key needed — just export your library from Apple Music and point Vibesort at the file. "
    "Genre tags from your local file collection fill enrichment gaps."
)

_am_xml_saved = (
    st.session_state.get("apple_music_xml_runtime")
    or getattr(cfg, "APPLE_MUSIC_XML_PATH", "").strip()
)

try:
    from core import apple_music as _am_mod_c
    _am_stats = _am_mod_c.library_stats(_am_xml_saved or None)
except Exception:
    _am_stats = {"available": False}

if _am_stats.get("available") and _am_xml_saved:
    _am_total = _am_stats.get("total_tracks", 0)
    _am_loved = _am_stats.get("loved", 0)
    _am_rated = _am_stats.get("rated_4plus", 0)
    st.success(
        f"✅ Apple Music library loaded — {_am_total:,} tracks · "
        f"{_am_loved} loved · {_am_rated} rated 4+"
    )
    st.caption(f"File: `{_am_xml_saved}`")
    if st.button("Remove Apple Music library", key="am_disconnect"):
        _update_env_key("APPLE_MUSIC_XML_PATH", "")
        try:
            cfg.APPLE_MUSIC_XML_PATH = ""
        except Exception:
            pass
        st.session_state.pop("apple_music_xml_runtime", None)
        st.rerun()
else:
    with st.form("apple_music_form"):
        st.markdown(
            "1. Open **Apple Music** (or iTunes)\n"
            "2. Go to **File → Library → Export Library...**\n"
            "3. Save the `.xml` file somewhere accessible\n"
            "4. Paste the full path below  _(or leave blank to use the default location)_"
        )
        _am_path_in = st.text_input(
            "Path to Music Library.xml",
            placeholder="~/Music/Music/Music Library.xml  (auto-detected if blank)",
            key="am_path_in",
        )
        _am_submit = st.form_submit_button("Load Apple Music Library", use_container_width=True)
        if _am_submit:
            _ampath = (_am_path_in or "").strip()
            # Expand ~ and env vars
            _ampath = os.path.expandvars(os.path.expanduser(_ampath)) if _ampath else ""
            try:
                from core import apple_music as _am_mod_c2
                _test_stats = _am_mod_c2.library_stats(_ampath or None)
                if _test_stats.get("available"):
                    _real_path = _test_stats["xml_path"]
                    _update_env_key("APPLE_MUSIC_XML_PATH", _real_path)
                    try:
                        cfg.APPLE_MUSIC_XML_PATH = _real_path
                    except Exception:
                        pass
                    st.session_state["apple_music_xml_runtime"] = _real_path
                    st.success(
                        f"✅ Found {_test_stats['total_tracks']:,} tracks "
                        f"({_test_stats['loved']} loved). Re-scan to use it."
                    )
                    st.rerun()
                else:
                    _default_paths = [
                        "~/Music/Music/Music Library.xml",
                        "~/Music/iTunes/iTunes Music Library.xml",
                    ]
                    st.error(
                        "Library file not found. Try exporting from Apple Music: "
                        "File → Library → Export Library..."
                    )
                    st.caption(
                        f"Default locations checked: {', '.join(_default_paths)}"
                        + (f" + `{_ampath}`" if _ampath else "")
                    )
            except Exception as _ame:
                st.error(f"Could not read library: {_ame}")

st.divider()

# ── Spotify streaming history import ─────────────────────────────────────────
st.subheader("Spotify Streaming History  ·  Play count boost")
st.caption(
    "Import your extended streaming history from Spotify to boost frequently-played tracks in playlists. "
    "Request your data at **spotify.com/account/privacy** — takes up to 30 days. "
    "Look for files named `StreamingHistory_music_*.json`."
)

_HISTORY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "streaming_history"
)
os.makedirs(_HISTORY_DIR, exist_ok=True)

_existing_history = sorted([
    f for f in os.listdir(_HISTORY_DIR)
    if f.endswith(".json")
]) if os.path.isdir(_HISTORY_DIR) else []

if _existing_history:
    _total_plays = 0
    for _hf in _existing_history:
        try:
            import json as _hjson
            with open(os.path.join(_HISTORY_DIR, _hf), "r", encoding="utf-8") as _hfh:
                _hdata = _hjson.load(_hfh)
            _total_plays += len(_hdata) if isinstance(_hdata, list) else 0
        except Exception:
            pass
    st.success(
        f"✅ {len(_existing_history)} streaming history file(s) loaded · "
        f"~{_total_plays:,} play records"
    )
    st.caption("Files: " + ", ".join(f"`{f}`" for f in _existing_history))
    if st.button("Remove streaming history", key="history_remove"):
        for _hf in _existing_history:
            try:
                os.remove(os.path.join(_HISTORY_DIR, _hf))
            except Exception:
                pass
        st.rerun()
else:
    _hist_files = st.file_uploader(
        "Drop your Spotify history files here",
        type=["json"],
        accept_multiple_files=True,
        key="history_uploader",
        help="Upload StreamingHistory_music_0.json, StreamingHistory_music_1.json, etc.",
    )
    if _hist_files:
        _saved = 0
        for _uf in _hist_files:
            try:
                _dest = os.path.join(_HISTORY_DIR, _uf.name)
                with open(_dest, "wb") as _dh:
                    _dh.write(_uf.getbuffer())
                _saved += 1
            except Exception as _he:
                st.warning(f"Could not save {_uf.name}: {_he}")
        if _saved:
            st.success(
                f"✅ {_saved} file(s) saved to `data/streaming_history/`. "
                "Re-scan to use your play history."
            )
            st.rerun()
    st.caption(
        "Don't have your history yet? Request it at "
        "[spotify.com/account/privacy](https://www.spotify.com/account/privacy) "
        "under **Download your data**."
    )

st.divider()

# ── Genius connection ─────────────────────────────────────────────────────────
st.subheader("Genius  ·  Lyrics enrichment (optional)")
st.caption(
    "Genius is used as a fallback lyrics source when lrclib.net and lyrics.ovh miss a track. "
    "Free API key at [genius.com/api-clients](https://genius.com/api-clients)."
)

_genius_key_saved = (
    st.session_state.get("genius_api_key_runtime")
    or getattr(cfg, "GENIUS_API_KEY", "").strip()
)

if _genius_key_saved:
    _masked_g = _genius_key_saved[:6] + "•" * 20 + _genius_key_saved[-4:]
    st.success(f"✅ Genius API key active ({_masked_g})")
    if st.button("Remove Genius key", key="genius_disconnect"):
        _update_env_key("GENIUS_API_KEY", "")
        try:
            cfg.GENIUS_API_KEY = ""
        except Exception:
            pass
        st.session_state.pop("genius_api_key_runtime", None)
        st.rerun()
else:
    with st.form("genius_form"):
        st.markdown(
            "1. Go to [genius.com/api-clients](https://genius.com/api-clients) and create a client\n"
            "2. Copy the **Client Access Token**\n"
            "3. Paste it below"
        )
        _g_key = st.text_input(
            "Genius Client Access Token",
            type="password",
            placeholder="Paste your Genius access token",
            key="genius_key_input",
        )
        _g_submit = st.form_submit_button("Save Genius key", use_container_width=True)
        if _g_submit:
            _gk = (_g_key or "").strip()
            if len(_gk) < 16:
                st.error("Key looks too short — check and try again.")
            else:
                _update_env_key("GENIUS_API_KEY", _gk)
                try:
                    cfg.GENIUS_API_KEY = _gk
                except Exception:
                    pass
                st.session_state["genius_api_key_runtime"] = _gk
                st.success("✅ Genius key saved. Re-scan to use it.")
                st.rerun()

st.divider()

# ── Own Spotify app (bypass 25-user Dev Mode limit) ───────────────────────────
with st.expander("Use your own Spotify app  ·  Bypass the 25-user limit"):
    st.markdown(
        """
Every Spotify account can create a **free developer app** at
[developer.spotify.com/dashboard](https://developer.spotify.com/dashboard).
With your own app, YOU are the only user — no quota limit, no whitelist needed.

**Setup (2 minutes):**
1. Go to the dashboard → **Create app**
2. Add redirect URI: `https://papakoftes.github.io/VibeSort/callback.html`
3. Copy your **Client ID** (the 32-char hex string — no secret needed)
4. Paste it below and click Save
        """
    )
    _own_id_current = getattr(cfg, "VIBESORT_CLIENT_ID", "").strip()
    _is_shared = _own_id_current == "c9e2d0ff7cbb49b0a59ca6c3b1c150bf"
    if _own_id_current and not _is_shared:
        _masked_id = _own_id_current[:6] + "•" * 20 + _own_id_current[-4:]
        st.success(f"✅ Using your own Spotify app ({_masked_id})")
        if st.button("Revert to shared app", key="sp_revert"):
            _default_id = "c9e2d0ff7cbb49b0a59ca6c3b1c150bf"
            _update_env_key("VIBESORT_CLIENT_ID", _default_id)
            try:
                cfg.VIBESORT_CLIENT_ID = _default_id
            except Exception:
                pass
            st.session_state.pop("pkce_auth_url", None)
            st.rerun()
    else:
        _own_id_input = st.text_input(
            "Your Spotify Client ID",
            placeholder="Paste your 32-character Client ID here",
            key="own_client_id_input",
        )
        if st.button("Save and reconnect with my app", key="sp_own_save"):
            _cid = (_own_id_input or "").strip()
            if len(_cid) < 16:
                st.error("Client ID looks too short — check it and try again.")
            else:
                ok = _update_env_key("VIBESORT_CLIENT_ID", _cid)
                try:
                    cfg.VIBESORT_CLIENT_ID = _cid
                except Exception:
                    pass
                # Force fresh PKCE URL and clear existing token so they re-auth
                st.session_state.pop("pkce_auth_url", None)
                for _k2 in ["spotify_token", "sp", "me", "pkce_token"]:
                    st.session_state.pop(_k2, None)
                if ok:
                    st.success("✅ Saved. Click **Connect to Spotify** above to re-authenticate with your app.")
                else:
                    st.warning(
                        "Active for this session — could not write to .env. "
                        "Add `VIBESORT_CLIENT_ID=<your_id>` manually for persistence."
                    )
                st.rerun()

st.divider()
with st.expander('Sharing with friends & going beyond the Spotify "test user" cap'):
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
  full "Sign in with Last.fm" style OAuth can be added later — Musixmatch is primarily
  API-key based for lyrics metadata.

Built-in sources (Deezer public search, lrclib, etc.) need no per-user login.
        """
    )
