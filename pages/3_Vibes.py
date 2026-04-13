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
from core.theme import inject, render_scan_quality_strip
from core.mood_graph import get_mood, mood_display_name

inject()

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
mood_results: dict     = vibesort.get("mood_results", {})
profiles: dict         = vibesort.get("profiles", {})
mood_fit_playlists: dict = vibesort.get("mood_fit_playlists", {})

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
        _obs_top = {
            t: float(max(1.0 - (i * 0.08), 0.3))
            for i, t in enumerate(mood_results.get(mood_name, {}).get("top_tags", [])[:8])
        }
        if "Middle-out" in naming_mode:
            name, desc = middle_out_name(
                [profiles[u] for u in uris if u in profiles],
                mood_name=mood_name,
                observed_tags=_obs_top,
            )
        elif "Top-down" in naming_mode:
            name, desc = top_down_name(
                mood_name,
                [profiles[u] for u in uris if u in profiles],
                observed_tags=_obs_top,
            )
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
render_scan_quality_strip(vibesort)
st.write("")

if not mood_results:
    mining_blocked = vibesort.get("mining_blocked", False)
    has_genres     = any(v for v in vibesort.get("artist_genres", {}).values() if v)
    has_audio      = bool(vibesort.get("audio_features", {}))

    if not has_genres and not has_audio and mining_blocked:
        st.warning(
            "**0 moods found — all three enrichment signals are unavailable:**\n\n"
            "- 🚫 **Audio features** — deprecated by Spotify (Nov 2024)\n"
            "- 🚫 **Artist genres** — your artists have no genre data on Spotify, "
            "and the batch genre endpoint is blocked in Development Mode\n"
            "- 🚫 **Playlist tags** — `playlist_items` is blocked in Development Mode\n\n"
            "**To fix this, you have two options:**\n\n"
            "**Option 1 — Quick (for personal use):** "
            "Go to [developer.spotify.com](https://developer.spotify.com) → Your App → "
            "Settings → User Management, and add your own Spotify account email. "
            "This unlocks playlist access for registered users.\n\n"
            "**Option 2 — Full production access:** "
            "Apply for [Extended Quota Mode](https://developer.spotify.com/documentation/web-api/concepts/quota-modes) "
            "to remove all Development Mode restrictions.",
        )
    elif not has_genres and mining_blocked:
        st.warning(
            "**0 moods found** — your artists have no genre data on Spotify and playlist "
            "mining is blocked. Try adding yourself as a test user in your Spotify app's "
            "User Management settings, then re-scan."
        )
    else:
        st.info(
            "No moods found. Your library may be too small, "
            "or the scan may not have enough genre/tag data. Try re-scanning."
        )
    if st.button("Re-scan Library"):
        st.switch_page("pages/2_Scan.py")
    st.stop()

# ── Mood Atlas ───────────────────────────────────────────────────────────────
with st.expander("🗺️ Mood Atlas — coverage across all moods", expanded=False):
    try:
        from core.mood_graph import all_moods as _all_moods_fn
        _all_moods_dict = _all_moods_fn()
        _all_mood_names = sorted(_all_moods_dict.keys())
        _total = len(_all_mood_names)

        # Build count lookup from mood_results
        _mood_count_lookup = {
            name: info.get("count", len(info.get("ranked", [])))
            for name, info in mood_results.items()
        }

        # Categorise by tier
        _strong  = [(n, _mood_count_lookup[n]) for n in _all_mood_names if _mood_count_lookup.get(n, 0) >= 15]
        _present = [(n, _mood_count_lookup[n]) for n in _all_mood_names if 8 <= _mood_count_lookup.get(n, 0) < 15]
        _thin    = [(n, _mood_count_lookup[n]) for n in _all_mood_names if 1 <= _mood_count_lookup.get(n, 0) < 8]
        _missing = [n for n in _all_mood_names if _mood_count_lookup.get(n, 0) == 0]

        st.caption(
            f"**{len(_strong) + len(_present) + len(_thin)}/{_total}** moods found in your library "
            f"({len(_strong)} strong, {len(_present)} present, {len(_thin)} thin)"
        )

        # Render in 4-column grid
        _atlas_entries = []
        for n, cnt in _strong:
            _atlas_entries.append(f"**{mood_display_name(n)}** ({cnt})")
        for n, cnt in _present:
            _atlas_entries.append(f"{mood_display_name(n)} ({cnt})")
        for n, cnt in _thin:
            _atlas_entries.append(f"~{mood_display_name(n)} ({cnt})")
        for n in _missing:
            _atlas_entries.append(f"~~{mood_display_name(n)}~~")

        _atlas_cols = st.columns(4)
        for _i, _entry in enumerate(_atlas_entries):
            _atlas_cols[_i % 4].markdown(_entry)
    except Exception as _e:
        st.caption(f"Atlas unavailable: {_e}")

# ── Discovery Gaps ───────────────────────────────────────────────────────────
# Show moods missing from the library with example tracks to inspire discovery
_missing_moods_for_gaps = []
try:
    from core.mood_graph import all_moods as _all_moods_gap_fn
    _all_moods_gap = _all_moods_gap_fn()
    _missing_moods_for_gaps = [
        n for n in sorted(_all_moods_gap.keys())
        if not mood_results.get(n) or mood_results[n].get("count", 0) == 0
    ]
except Exception:
    pass

if _missing_moods_for_gaps:
    with st.expander(f"🌱 Discovery Gaps — {len(_missing_moods_for_gaps)} unexplored vibes", expanded=False):
        st.caption(
            "These moods have no tracks in your library yet. "
            "The example tracks below are curated anchors for each vibe — "
            "adding a few to your Spotify library will unlock that mood on your next scan."
        )
        try:
            from core.anchors import load_mood_anchors as _lma_gap
            _anchors_gap = _lma_gap() or {}
        except Exception:
            _anchors_gap = {}

        _gap_cols = st.columns(3)
        for _gi, _gap_mood in enumerate(_missing_moods_for_gaps[:18]):  # cap at 18
            with _gap_cols[_gi % 3]:
                with st.container(border=True):
                    st.markdown(f"**{mood_display_name(_gap_mood)}**")
                    try:
                        from core.mood_graph import get_mood as _gm_gap
                        _gm_pack = _gm_gap(_gap_mood) or {}
                        if _gm_pack.get("description"):
                            st.caption(_gm_pack["description"])
                    except Exception:
                        pass
                    _ex_tracks = _anchors_gap.get(_gap_mood, [])[:3]
                    if _ex_tracks:
                        for _ex in _ex_tracks:
                            _ex_a = _ex.get("artist", "")
                            _ex_t = _ex.get("title", "")
                            if _ex_a and _ex_t:
                                st.markdown(f"- *{_ex_t}* — {_ex_a}")
                    else:
                        st.caption("No example tracks yet.")

        if len(_missing_moods_for_gaps) > 18:
            st.caption(f"… and {len(_missing_moods_for_gaps) - 18} more unexplored vibes.")

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
                st.markdown(f"### {mood_display_name(mood_name)}")
                try:
                    pack = get_mood(mood_name) or {}
                    desc = pack.get("description", "")
                    if desc:
                        st.caption(desc)
                except Exception:
                    pass

                try:
                    from core.cohesion import cohesion_label as _clabel
                    _clabel_str = _clabel(cohesion)
                except Exception:
                    _clabel_str = f"{cohesion * 100:.0f}%"
                st.caption(f"{count} tracks · {_clabel_str} ({min(cohesion, 1.0) * 100:.0f}%)")
                st.progress(min(max(float(cohesion), 0.0), 1.0), text="")

                top = _top_tracks_display(uris, n=3)
                for t in top:
                    st.markdown(f"- {t}")

                top_tags = info.get("top_tags", [])
                if top_tags:
                    st.caption("🏷 " + " · ".join(top_tags[:5]))

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
            st.markdown(f"#### {mood_display_name(mood_name)} — Full Tracklist ({len(uris)} tracks)")

            # Build mood slug for tag matching
            _slug = mood_name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
            while "__" in _slug:
                _slug = _slug.replace("__", "_")
            _slug = _slug.strip("_")

            # Load track tags for signal badges
            track_tags_all = vibesort.get("track_tags", {})

            # Show all tracks
            track_rows = []
            for uri in uris:
                p = profiles.get(uri, {})
                if p:
                    artists = ", ".join(p.get("artists", [])[:2])
                    tags = track_tags_all.get(uri, {}) or {}

                    # Build signal badges
                    badges = []
                    if tags.get(f"anchor_{_slug}", 0) == 1.0:
                        badges.append("🔑 Anchor")
                    if tags.get(f"personal_anchor_{_slug}", 0) > 0:
                        badges.append("🎵 Personal")
                    if tags.get(f"graph_mood_{_slug}", 0) > 0.3:
                        badges.append("🕸️ Similar")
                    if tags.get(f"mood_{_slug}", 0) > 0.3:
                        badges.append("📻 Last.fm")
                    lyr_tags = [k for k, v in tags.items() if k.startswith("lyr_") and v > 0.3]
                    if lyr_tags:
                        lyr_label = lyr_tags[0].replace("lyr_", "")
                        badges.append(f"📖 Lyrics: {lyr_label}")
                    # Time-of-day badge
                    _tod_labels = {
                        "tod_late_night": "🌙 Late Night",
                        "tod_morning":    "🌅 Morning",
                        "tod_afternoon":  "☀️ Afternoon",
                        "tod_evening":    "🌆 Evening",
                    }
                    for _tk, _tl in _tod_labels.items():
                        if tags.get(_tk, 0) >= 0.5:
                            badges.append(_tl)
                            break
                    macro = (p.get("macro_genres") or [])
                    if macro:
                        badges.append(macro[0])

                    badge_str = " ".join(f"[{b}]" for b in badges)
                    line = f"**{p.get('name', '')}** — {artists}"
                    if badge_str:
                        line += f" {badge_str}"
                    track_rows.append(line)
            for i in range(0, len(track_rows), 3):
                chunk = track_rows[i:i+3]
                tcols = st.columns(3)
                for tc, row in zip(tcols, chunk):
                    tc.markdown(f"- {row}")

            # ── Public playlists you'd fit into ──────────────────────────────
            fit_playlists = mood_fit_playlists.get(mood_name, [])
            if fit_playlists:
                st.divider()
                st.markdown("**🌐 Public playlists you'd fit right into**")
                st.caption(
                    "Spotify community playlists that share the most songs with your library "
                    "for this vibe. Great for discovering new music in the same territory."
                )
                for pl in fit_playlists[:5]:
                    pl_name    = pl.get("name", "Untitled")
                    pl_overlap = pl.get("count", pl.get("overlap_count", 0))
                    pl_follows = pl.get("followers", 0)
                    pl_id      = pl.get("id", "")
                    pl_url     = f"https://open.spotify.com/playlist/{pl_id}" if pl_id else ""
                    follows_str = (
                        f"{pl_follows:,} followers · " if pl_follows else ""
                    )
                    overlap_str = f"{pl_overlap} songs in common"
                    if pl_url:
                        st.markdown(
                            f"- [{pl_name}]({pl_url}) — {follows_str}{overlap_str}"
                        )
                    else:
                        st.markdown(f"- **{pl_name}** — {follows_str}{overlap_str}")

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
