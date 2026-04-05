"""
app.py — Vibesort Home.

Default landing page.  Routing logic:
  • No Spotify token  → connect prompt inline
  • Token + no scan   → scan prompt + enrichment status
  • Token + scan done → library dashboard + quick nav
"""

import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Vibesort",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help":    "https://github.com/PapaKoftes/VibeSort",
        "Report a bug":"https://github.com/PapaKoftes/VibeSort/issues",
        "About": (
            "## Vibesort\n"
            "**Your Spotify library, sorted by feeling.**\n\n"
            "Reads your Spotify library and builds mood, genre, era, and artist playlists "
            "using a multi-signal engine: playlist tags · lyrics · genre data.\n\n"
            "Open source · [github.com/PapaKoftes/VibeSort](https://github.com/PapaKoftes/VibeSort)"
        ),
    },
)

from core.theme import inject, render_scan_quality_strip
from core.mood_graph import mood_display_name

inject()

# ── OAuth callback interception ───────────────────────────────────────────────
# The GitHub Pages proxy always redirects to the root URL (?code=...).
_code  = st.query_params.get("code")
_state = st.query_params.get("state", "")
if _code:
    st.session_state["_pending_code"]  = _code
    st.session_state["_pending_state"] = _state
    st.query_params.clear()

import config as cfg

# ── Session state defaults (prevent KeyError on first load / rerun) ───────────
st.session_state.setdefault("observed_mood_tags",   {})
st.session_state.setdefault("user_tag_prefs",        {})
st.session_state.setdefault("query",                 None)
st.session_state.setdefault("strictness",            3)
st.session_state.setdefault("playlist_min_score",    0.25)
st.session_state.setdefault("playlist_min_size",     20)
st.session_state.setdefault("playlist_expansion",    True)
st.session_state.setdefault("allow_mvp_fallback",    getattr(cfg, "ALLOW_MVP_FALLBACK", True))
st.session_state.setdefault("scan_corpus_mode",      "full_library")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _feature_status() -> dict:
    """Return dict of which enrichment sources are configured/active."""
    vibesort   = st.session_state.get("vibesort", {})
    scan_flags = vibesort.get("scan_flags", {})
    return {
        "spotify":       bool(st.session_state.get("spotify_token")),
        "lastfm":        bool(getattr(cfg, "LASTFM_API_KEY",    "").strip()),
        "listenbrainz":  bool(getattr(cfg, "LISTENBRAINZ_TOKEN","").strip()),
        "genius":        bool(getattr(cfg, "GENIUS_API_KEY",   "").strip()),
        "deezer":        True,
        "lyrics":        True,
        "has_audio":        scan_flags.get("has_audio",        False),
        "has_tags":         scan_flags.get("has_tags",         False),
        "has_genres":       scan_flags.get("has_genres",       False),
        "has_lyrics":       scan_flags.get("has_lyrics",       False),
        "has_listenbrainz": scan_flags.get("has_listenbrainz", False),
        "has_discogs":      scan_flags.get("has_discogs",      True),
        "has_genius_flag":  scan_flags.get("has_genius",       False),
    }


def _status_dot(ok: bool) -> str:
    return "🟢" if ok else "🔴"


def _library_data_story(vibesort: dict) -> str:
    """
    Human read on enrichment outputs (genres, tags, lyrics) — not mood playlist sizes.
    """
    gm = vibesort.get("genre_map", {}) or {}
    prefs = vibesort.get("user_tag_prefs", {}) or {}
    profiles = vibesort.get("profiles", {}) or {}
    track_tags = vibesort.get("track_tags", {}) or {}

    parts: list[str] = []

    non_other = sorted(
        ((g, len(uris)) for g, uris in gm.items() if g != "Other"),
        key=lambda x: -x[1],
    )
    other_n = len(gm.get("Other", []))
    if non_other:
        head = ", ".join(f"**{g}** ({n})" for g, n in non_other[:3])
        parts.append(f"Your macro-genre footprint clusters around {head}.")
        if other_n:
            parts.append(
                f"**{other_n}** tracks are still in the broad *Other* bucket "
                "(unusual Spotify genre strings — mapping improves over time)."
            )

    if prefs:
        top_t = sorted(prefs.items(), key=lambda x: -x[1])[:8]
        ttxt = " · ".join(t.replace("_", " ") for t, _ in top_t)
        parts.append(f"From playlist mining and tag sources, recurring textures include *{ttxt}*.")

    n_lyr = sum(
        1
        for ut in track_tags.values()
        if any(str(k).lower().startswith("lyr_") for k in (ut or {}))
    )
    n_prof = len(profiles)
    if n_prof and n_lyr:
        pct = round(100 * n_lyr / max(n_prof, 1))
        parts.append(
            f"**{pct}%** of tracks carry lyric-derived mood tags — those power lyric-led playlist names and scoring."
        )

    return (
        " ".join(parts)
        if parts
        else "Run a full scan with Last.fm (optional) and lyrics on for the richest interpretation of your library."
    )


def _render_enrichment_panel(feat: dict) -> None:
    """Render the compact enrichment status in the sidebar."""
    st.markdown("#### Data sources")

    # Spotify
    sp_ok = feat["spotify"]
    st.markdown(f"{_status_dot(sp_ok)} **Spotify** {'connected' if sp_ok else 'not connected'}")

    # Built-in sources (always green)
    st.markdown("🟢 **Deezer genres** built-in")
    st.markdown("🟢 **Discogs styles** built-in")
    st.markdown("🟢 **Lyrics** built-in (lrclib + lyrics.ovh)")

    g_ok = feat["genius"]
    st.markdown(
        f"{_status_dot(g_ok)} **Genius** {'active (lyrics fallback)' if g_ok else '— add GENIUS_API_KEY for extra coverage'}"
    )

    # Optional sources (key required)
    lf_ok = feat["lastfm"]
    st.markdown(
        f"{_status_dot(lf_ok)} **Last.fm** {'active' if lf_ok else '— add key for richer tags'}"
    )

    lb_ok = feat["listenbrainz"]
    st.markdown(
        f"{_status_dot(lb_ok)} **ListenBrainz** {'active' if lb_ok else '— add token to boost your favourites'}"
    )

    st.divider()

    # Active signal quality
    if feat["spotify"]:
        audio_s = "✅ audio"  if feat["has_audio"]        else "⚠️ audio blocked"
        tags_s  = "✅ tags"   if feat["has_tags"]         else "⚠️ no tags"
        genre_s = "✅ genres" if feat["has_genres"]       else "⚠️ no genres"
        lyr_s   = "✅ lyrics" if feat["has_lyrics"]       else "—"
        lb_s    = "✅ lb"     if feat["has_listenbrainz"] else "—"
        st.caption(f"Last scan: {audio_s} · {tags_s} · {genre_s} · {lyr_s} · {lb_s}")

    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/9_Settings.py")


def _home():
    """Home page content — called directly or via st.navigation."""
    connected = bool(st.session_state.get("spotify_token"))
    has_scan  = bool(st.session_state.get("vibesort"))
    feat      = _feature_status()

    with st.sidebar:
        _render_enrichment_panel(feat)

    st.markdown("# 🎧 Vibesort")

    if not connected:
        # ── Not connected ─────────────────────────────────────────────────────
        st.markdown("*Your library, sorted by feeling.*")
        st.divider()

        col_cta, col_gap, col_info = st.columns([2, 0.2, 1.8])

        with col_cta:
            st.markdown("### Connect your Spotify")
            st.markdown(
                "Vibesort reads your Spotify library and builds playlists sorted by feeling — "
                "mood, genre, era, and artist — powered by playlist mining, lyrics, and genre data."
            )
            st.markdown("")
            if st.button("Connect to Spotify →", type="primary", use_container_width=True):
                st.switch_page("pages/1_Connect.py")

        with col_info:
            st.markdown("**What you get**")
            st.markdown(
                "- 🎭 Rich mood packs (niche + lyric-led) matched to your taste\n"
                "- 🎸 Genre & era playlists auto-generated\n"
                "- 🧬 Taste Map — your music DNA visualised\n"
                "- 🎨 Artist spotlights for your top artists\n"
                "- 📦 One-click deploy to Spotify"
            )

    elif not has_scan:
        # ── Connected but no scan ─────────────────────────────────────────────
        user = st.session_state.get("me", {})
        name = user.get("display_name") or "there"

        st.markdown(f"*Hey {name} — your library is ready to sort.*")
        st.divider()

        col_scan, col_gap, col_status = st.columns([2, 0.2, 1.8])

        with col_scan:
            st.markdown("### Scan your library")
            st.markdown(
                "A scan collects your liked songs, top tracks, and artists — then enriches "
                "everything with genre, mood, and lyric data. Takes 1–3 minutes depending on library size."
            )
            st.markdown("")

            # Show what enrichment will run
            notes = [
                "✅ Deezer genres + Discogs styles (built-in)",
                "✅ Lyrics via lrclib + lyrics.ovh",
            ]
            if feat["genius"]:
                notes.append("✅ Genius lyrics fallback")
            else:
                notes.append("ℹ️ Optional: GENIUS_API_KEY in .env for higher lyric coverage")
            if feat["lastfm"]:
                notes.append("✅ Last.fm mood tags")
            else:
                notes.append("⚠️ Last.fm not configured — add LASTFM_API_KEY to .env for better results")
            for n in notes:
                st.markdown(f"  {n}")

            st.markdown("")
            if st.button("Scan Library →", type="primary", use_container_width=True):
                st.switch_page("pages/2_Scan.py")

        with col_status:
            st.markdown("**Enrichment quality without extra keys**")
            st.markdown(
                "Genre matching works out of the box via Deezer. "
                "Add a free Last.fm key to get stronger mood and context matching."
            )
            st.markdown("[Get Last.fm key →](https://www.last.fm/api/account/create)")

    else:
        # ── Connected + scanned — dashboard ──────────────────────────────────
        vibesort      = st.session_state["vibesort"]
        _corpus_mode  = vibesort.get("scan_meta", {}).get("corpus_mode", st.session_state.get("scan_corpus_mode", "full_library"))
        mood_results  = vibesort.get("mood_results",  {})
        profiles      = vibesort.get("profiles",      {})
        genre_map     = vibesort.get("genre_map",     {})
        era_map       = vibesort.get("era_map",       {})
        artist_map    = vibesort.get("artist_map",    {})
        user          = st.session_state.get("me", {})
        name          = user.get("display_name") or ""

        n_tracks  = len(profiles)
        n_moods   = len(mood_results)
        n_genres  = sum(1 for g, uris in genre_map.items() if g != "Other" and len(uris) >= 5)
        n_artists = len(artist_map)

        _corpus_label = "Liked songs only" if _corpus_mode == "liked_only" else "Full library"
        greeting = f"*{name}'s library* · {_corpus_label}" if name else f"*Your library* · {_corpus_label}"
        st.markdown(greeting)

        # ── Quick stats ───────────────────────────────────────────────────────
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tracks", f"{n_tracks:,}")
        c2.metric("Moods",  n_moods)
        c3.metric("Genres", n_genres)
        c4.metric("Artists",n_artists)

        st.divider()
        render_scan_quality_strip(vibesort, title="Current Scan Quality")
        st.divider()

        # ── Navigation cards ──────────────────────────────────────────────────
        col_v, col_g, col_t, col_a, col_s, col_b, col_stats = st.columns(7)

        with col_v:
            st.markdown("### 🎭 Vibes")
            st.caption(f"{n_moods} mood playlists ready")
            if st.button("Open Vibes", use_container_width=True, type="primary"):
                st.switch_page("pages/3_Vibes.py")

        with col_g:
            st.markdown("### 🎸 Genres")
            st.caption(f"{n_genres} genre playlists")
            if st.button("Open Genres", use_container_width=True):
                st.switch_page("pages/4_Genres.py")

        with col_t:
            st.markdown("### 🧬 Taste Map")
            st.caption("Your music DNA")
            if st.button("Open Taste Map", use_container_width=True):
                st.switch_page("pages/6_Taste_Map.py")

        with col_a:
            st.markdown("### 🎤 Artists")
            st.caption(f"{n_artists} spotlights")
            if st.button("Open Artists", use_container_width=True):
                st.switch_page("pages/5_Artists.py")

        with col_s:
            st.markdown("### 📦 Staging")
            try:
                from staging import staging as _sm
                staged = _sm.get_staged_count()
            except Exception:
                staged = len(st.session_state.get("staged_ids", []))
            st.caption(f"{staged} playlists ready to deploy")
            if st.button("Open Staging", use_container_width=True):
                st.switch_page("pages/7_Staging.py")

        with col_b:
            st.markdown("### 🤝 Blend")
            st.caption("Cross-user overlap blends")
            if st.button("Open Blend", use_container_width=True):
                st.switch_page("pages/6_Blend.py")

        with col_stats:
            st.markdown("### 📊 Stats")
            st.caption("Taste report + analytics")
            if st.button("Open Stats", use_container_width=True):
                st.switch_page("pages/8_Stats.py")

        # ── Library interpretation (data collected) + mood sizes (secondary) ───
        if mood_results:
            st.divider()
            st.markdown("#### How your library reads")
            st.info(_library_data_story(vibesort))
            with st.expander("Mood playlist sizes (scoring output — reference)", expanded=False):
                st.caption(
                    "These counts are how many tracks scored into each vibe pack after dedup — "
                    "useful for staging, not the same as raw genre/tag totals above."
                )
                sorted_moods = sorted(
                    mood_results.items(),
                    key=lambda x: -len(x[1].get("ranked", [])),
                )[:8]
                cols = st.columns(4)
                for i, (mood_name, data) in enumerate(sorted_moods):
                    ranked = data.get("ranked", [])
                    cohesion = data.get("cohesion", 0)
                    with cols[i % 4]:
                        st.markdown(f"**{mood_display_name(mood_name)}**")
                        st.caption(f"{len(ranked)} tracks · {cohesion:.0%} cohesion")

        # ── Rescan button ─────────────────────────────────────────────────────
        st.divider()
        col_rs, _ = st.columns([1, 3])
        with col_rs:
            if st.button("↺ Rescan Library", use_container_width=True):
                st.switch_page("pages/2_Scan.py")


# ── Entry point ───────────────────────────────────────────────────────────────
# Use st.navigation (Streamlit >= 1.36) to give pages proper display names,
# including renaming the home page from "app" to "Home".
# Falls back to direct _home() call on older Streamlit versions.

if hasattr(st, "navigation"):
    _pg = st.navigation(
        [
            st.Page(_home,                       title="Home",     icon="🏠", default=True),
            st.Page("pages/1_Connect.py",        title="Connect"),
            st.Page("pages/2_Scan.py",           title="Scan"),
            st.Page("pages/3_Vibes.py",          title="Vibes"),
            st.Page("pages/4_Genres.py",         title="Genres"),
            st.Page("pages/5_Artists.py",        title="Artists"),
            st.Page("pages/6_Taste_Map.py",      title="Taste Map"),
            st.Page("pages/6_Blend.py",          title="Blend"),
            st.Page("pages/7_Staging.py",        title="Staging"),
            st.Page("pages/8_Stats.py",          title="Stats"),
            st.Page("pages/9_Settings.py",       title="Settings"),
        ],
        position="sidebar",
    )
    _pg.run()
else:
    # Streamlit < 1.36 — old multipage model; home content runs directly.
    _home()
