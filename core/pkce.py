"""
core/pkce.py — Spotify PKCE OAuth flow (no client secret needed).

Lets the developer embed their Spotify Client ID so end users
never have to create a Spotify Developer app.

Flow:
  1. generate_auth_url()  — builds the Spotify auth URL, saves state to disk
  2. User authorizes on Spotify
  3. Spotify → GitHub Pages callback → localhost:8501?code=...
  4. exchange_code(code)  — loads state from disk, exchanges for tokens
  5. Returns (access_token, refresh_token, expires_in)

Token refresh:
  refresh_token_request(refresh_token, client_id)
"""

import hashlib
import base64
import secrets
import json
import os
import time
import requests as _requests

_ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATE_FILE = os.path.join(_ROOT, ".vibesort_pkce_state")
_TOKEN_FILE = os.path.join(_ROOT, ".vibesort_cache")

TOKEN_URL    = "https://accounts.spotify.com/api/token"
AUTH_URL     = "https://accounts.spotify.com/authorize"


# ── PKCE helpers ──────────────────────────────────────────────────────────────

def _generate_verifier() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ── Auth URL ──────────────────────────────────────────────────────────────────

def generate_auth_url(client_id: str, redirect_uri: str, scope: str) -> str:
    """
    Generate a Spotify PKCE authorization URL.
    Saves verifier + state to disk so exchange_code() can use them
    after the page reloads from the OAuth redirect.
    """
    from urllib.parse import urlencode

    verifier  = _generate_verifier()
    challenge = _challenge(verifier)
    state     = secrets.token_hex(16)

    from core.cache_io import atomic_write_json
    atomic_write_json(
        _STATE_FILE,
        {"verifier": verifier, "state": state, "ts": time.time()},
    )

    params = {
        "client_id":             client_id,
        "response_type":         "code",
        "redirect_uri":          redirect_uri,
        "code_challenge_method": "S256",
        "code_challenge":        challenge,
        "scope":                 scope,
        "state":                 state,
        "show_dialog":           "false",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


# ── Code exchange ─────────────────────────────────────────────────────────────

def exchange_code(code: str, client_id: str, redirect_uri: str,
                  returned_state: str = "") -> dict:
    """
    Exchange an authorization code for tokens.
    Loads the verifier saved by generate_auth_url().

    Returns a dict with: access_token, refresh_token, expires_in, token_type, scope
    Raises on failure.
    """
    if not os.path.exists(_STATE_FILE):
        raise RuntimeError("PKCE state file missing — please re-authorize.")

    with open(_STATE_FILE, "r", encoding="utf-8") as f:
        saved = json.load(f)

    # Clean up state file
    try:
        os.remove(_STATE_FILE)
    except OSError:
        pass

    verifier = saved.get("verifier")
    if not verifier:
        raise RuntimeError("PKCE verifier not found in state.")

    # CSRF check: state param Spotify returns must match what we sent
    if returned_state and saved.get("state") and returned_state != saved["state"]:
        raise RuntimeError("PKCE state mismatch — possible CSRF. Please re-authorize.")

    resp = _requests.post(TOKEN_URL, data={
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  redirect_uri,
        "client_id":     client_id,
        "code_verifier": verifier,
    })

    if not resp.ok:
        raise RuntimeError(f"Token exchange failed: {resp.status_code} — {resp.text}")

    token = resp.json()
    token["expires_at"] = int(time.time()) + token.get("expires_in", 3600)
    return token


# ── Token refresh ─────────────────────────────────────────────────────────────

def refresh_access_token(refresh_token: str, client_id: str) -> dict:
    """
    Refresh an access token. Returns updated token dict.
    No client_secret needed with PKCE.
    """
    resp = _requests.post(TOKEN_URL, data={
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
        "client_id":     client_id,
    })
    if not resp.ok:
        raise RuntimeError(f"Token refresh failed: {resp.status_code} — {resp.text}")

    token = resp.json()
    token["expires_at"] = int(time.time()) + token.get("expires_in", 3600)
    if "refresh_token" not in token:
        token["refresh_token"] = refresh_token  # reuse old one if not rotated
    return token


# ── Persistent token cache ────────────────────────────────────────────────────

def save_token(token: dict) -> None:
    """Persist PKCE token to disk so it survives app restarts."""
    try:
        from core.cache_io import atomic_write_json
        atomic_write_json(_TOKEN_FILE, {"pkce": token})
    except OSError:
        pass


def load_token() -> dict | None:
    """Load cached PKCE token from disk. Returns None if missing/corrupt."""
    if not os.path.exists(_TOKEN_FILE):
        return None
    try:
        with open(_TOKEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("pkce")
    except Exception:
        return None


def clear_token() -> None:
    """Delete cached token (on disconnect)."""
    try:
        if os.path.exists(_TOKEN_FILE):
            os.remove(_TOKEN_FILE)
    except OSError:
        pass


# ── Build spotipy client from token ──────────────────────────────────────────

def make_spotify(token: dict, client_id: str):
    """
    Build a spotipy.Spotify instance from a PKCE token dict.
    Handles auto-refresh transparently.
    """
    import spotipy
    import time

    access_token = token.get("access_token")

    # Refresh if expired
    if token.get("expires_at", 0) - time.time() < 60:
        rt = token.get("refresh_token")
        if rt:
            token = refresh_access_token(rt, client_id)
            access_token = token["access_token"]

    return spotipy.Spotify(auth=access_token), token
