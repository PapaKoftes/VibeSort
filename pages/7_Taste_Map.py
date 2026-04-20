"""
pages/7_Taste_Map.py — Music DNA & Taste Compatibility.

Your library fingerprinted into a shareable profile.
Export yours, import a friend's, see where you overlap.
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(page_title="Vibesort — Taste Map", page_icon="🎧", layout="wide")
from core.theme import inject, render_scan_quality_strip
inject()

if not st.session_state.get("spotify_token"):
    st.warning("Please connect to Spotify first.")
    if st.button("Connect"):
        st.switch_page("pages/1_Connect.py")
    st.stop()

vibesort = st.session_state.get("vibesort")
if not vibesort:
    st.info("Scan your library first to generate your Taste Map.")
    if st.button("Scan Library", type="primary"):
        st.switch_page("pages/2_Scan.py")
    st.stop()

_EXPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "outputs", "taste_map.json"
)

# ── Build fingerprint from scan data ─────────────────────────────────────────

def _build_fingerprint(vs: dict) -> dict:
    """Distill the scan into a compact, shareable fingerprint."""
    from core.genre import to_macro

    me       = st.session_state.get("me", {})
    profiles = vs.get("profiles", {})
    tracks   = vs.get("all_tracks", [])
    genre_map = vs.get("genre_map", {})
    era_map   = vs.get("era_map", {})
    artist_map = vs.get("artist_map", {})
    mood_results = vs.get("mood_results", {})
    track_tags = vs.get("track_tags", {})

    total = len(tracks)

    # ── Genre distribution (top 10, non-exclusive membership share) ─────────
    genre_dist: dict[str, float] = {}
    for genre, uris in genre_map.items():
        if genre != "Other":
            genre_dist[genre] = round(len(uris) / max(total, 1), 4)
    genre_dist = dict(sorted(genre_dist.items(), key=lambda x: -x[1])[:10])

    # Exclusive primary genre distribution (each track contributes to one genre)
    primary_genre_counts: dict[str, int] = {}
    for p in profiles.values():
        macros = [g for g in p.get("macro_genres", []) if g != "Other"]
        if not macros:
            continue
        g0 = macros[0]
        primary_genre_counts[g0] = primary_genre_counts.get(g0, 0) + 1
    primary_genre_dist = {
        g: round(c / max(total, 1), 4)
        for g, c in sorted(primary_genre_counts.items(), key=lambda x: -x[1])[:10]
    }

    # ── Era distribution ─────────────────────────────────────────────────────
    era_dist: dict[str, float] = {}
    for era, uris in era_map.items():
        era_dist[era] = round(len(uris) / max(total, 1), 4)

    # ── Top artists (name + genre list) ─────────────────────────────────────
    top_artists = []
    artist_genres_map = vs.get("artist_genres", {})
    _artist_name_id_counts: dict[tuple[str, str], int] = {}
    for t in tracks:
        for a in t.get("artists", []):
            an = a.get("name")
            aid = a.get("id")
            if an and aid:
                _artist_name_id_counts[(an, aid)] = _artist_name_id_counts.get((an, aid), 0) + 1
    for name, uris in sorted(artist_map.items(), key=lambda x: -len(x[1]))[:20]:
        _candidates = [(aid, c) for (an, aid), c in _artist_name_id_counts.items() if an == name]
        aid = sorted(_candidates, key=lambda x: -x[1])[0][0] if _candidates else None
        top_artists.append({
            "name":   name,
            "tracks": len(uris),
            "genres": artist_genres_map.get(aid, [])[:3] if aid else [],
        })

    # ── Audio profile (mean excluding neutral vectors, aligned with profile logic)
    from core.profile import user_audio_mean as _user_audio_mean
    mean_vec = _user_audio_mean(profiles)
    vecs = [mean_vec] if mean_vec else []
    if vecs:
        mean_vec = [round(v, 3) for v in mean_vec]
        audio_profile = {
            "energy":           mean_vec[0],
            "valence":          mean_vec[1],
            "danceability":     mean_vec[2],
            "tempo_norm":       mean_vec[3],
            "acousticness":     mean_vec[4],
            "instrumentalness": mean_vec[5],
        }
    else:
        audio_profile = {}

    # ── Taste tags (most common tags from playlist mining) ────────────────────
    # Filter out internal expansion artifacts and Last.fm noise that slip through
    _TASTE_NOISE: frozenset[str] = frozenset({
        # Last.fm noise / personal tags
        "seen_live", "seen live", "favorite", "favourite", "favorites",
        "favourites", "love", "liked", "loved", "awesome", "great", "good",
        "amazing", "best", "beautiful", "cool", "nice", "top", "all",
        "music", "songs", "playlist", "mix", "tracks", "hits",
        "heard_on_pandora", "spotify", "youtube",
        # BASIC_MAP expansion artifacts (too generic to be meaningful taste tags)
        "pump", "relax", "smooth", "gentle", "mellow", "bright", "dance",
        "sophisticated", "anger", "freedom",
        # Very short / unhelpful
        "lp", "ep", "uk", "us",
    })

    tag_counter: dict[str, float] = {}
    lyrical_tag_counter: dict[str, float] = {}
    for uri_tags in track_tags.values():
        for tag, w in uri_tags.items():
            if tag.startswith("lyr_"):
                lyrical_tag_counter[tag[4:]] = lyrical_tag_counter.get(tag[4:], 0.0) + float(w)
                continue
            tag_lower = tag.lower().replace(" ", "_")
            if tag_lower in _TASTE_NOISE:
                continue
            if len(tag) < 3:
                continue
            tag_counter[tag] = tag_counter.get(tag, 0) + w
    taste_tags = dict(sorted(tag_counter.items(), key=lambda x: -x[1])[:20])
    lyrical_tags = dict(sorted(lyrical_tag_counter.items(), key=lambda x: -x[1])[:12])

    # ── Mood strengths ────────────────────────────────────────────────────────
    mood_strengths = {
        m: {"count": v["count"], "cohesion": round(v["cohesion"], 3)}
        for m, v in mood_results.items()
    }

    return {
        "version":       2,
        "display_name":  me.get("display_name") or me.get("id", "Unknown"),
        "total_tracks":  total,
        "genre_dist":    genre_dist,
        "primary_genre_dist": primary_genre_dist,
        "era_dist":      era_dist,
        "top_artists":   top_artists,
        "audio_profile": audio_profile,
        "taste_tags":    taste_tags,
        "lyrical_tags":  lyrical_tags,
        "mood_strengths": mood_strengths,
        "exported_at":   time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _compat_score(mine: dict, theirs: dict) -> dict:
    """Compute taste compatibility between two fingerprints."""
    # Genre overlap
    my_genres    = set(mine.get("genre_dist", {}).keys())
    their_genres = set(theirs.get("genre_dist", {}).keys())
    genre_overlap = my_genres & their_genres
    genre_score   = round(len(genre_overlap) / max(len(my_genres | their_genres), 1), 3)

    # Artist overlap
    my_artists    = {a["name"] for a in mine.get("top_artists", [])}
    their_artists = {a["name"] for a in theirs.get("top_artists", [])}
    artist_overlap = my_artists & their_artists
    artist_score   = round(len(artist_overlap) / max(len(my_artists | their_artists), 1), 3)

    # Mood overlap (shared moods)
    my_moods    = set(mine.get("mood_strengths", {}).keys())
    their_moods = set(theirs.get("mood_strengths", {}).keys())
    mood_overlap = my_moods & their_moods
    mood_score   = round(len(mood_overlap) / max(len(my_moods | their_moods), 1), 3)

    # Audio profile distance (only if both have it)
    audio_score = 0.5  # neutral default
    ma, ta = mine.get("audio_profile"), theirs.get("audio_profile")
    if ma and ta:
        keys = ["energy", "valence", "danceability", "tempo_norm", "acousticness", "instrumentalness"]
        diffs = [abs(ma.get(k, 0.5) - ta.get(k, 0.5)) for k in keys]
        audio_score = round(1.0 - (sum(diffs) / len(diffs)), 3)

    # Tag overlap
    my_tags    = set(mine.get("taste_tags", {}).keys())
    their_tags = set(theirs.get("taste_tags", {}).keys())
    tag_overlap = my_tags & their_tags
    tag_score   = round(len(tag_overlap) / max(len(my_tags | their_tags), 1), 3)

    overall = round(
        0.25 * genre_score +
        0.25 * artist_score +
        0.20 * mood_score +
        0.15 * audio_score +
        0.15 * tag_score,
        3,
    )

    return {
        "overall":        overall,
        "genre_score":    genre_score,
        "artist_score":   artist_score,
        "mood_score":     mood_score,
        "audio_score":    audio_score,
        "tag_score":      tag_score,
        "common_genres":  sorted(genre_overlap),
        "common_artists": sorted(artist_overlap),
        "common_moods":   sorted(mood_overlap),
        "common_tags":    sorted(tag_overlap)[:15],
        "your_unique":    sorted(my_genres - their_genres),
        "their_unique":   sorted(their_genres - my_genres),
    }


# ── Page ──────────────────────────────────────────────────────────────────────

st.title("Taste Map")
render_scan_quality_strip(vibesort)
st.write("")
st.caption("Your music DNA — export it, share it, compare it.")
st.divider()

# Build / cache fingerprint in session and invalidate on new scan/corpus mode.
_scan_meta = vibesort.get("scan_meta", {})
_fp_cache_key = (
    _scan_meta.get("corpus_mode", "full_library"),
    len(vibesort.get("all_tracks", [])),
    len(vibesort.get("mood_results", {})),
)
if st.session_state.get("taste_fingerprint_key") != _fp_cache_key:
    st.session_state["taste_fingerprint"] = _build_fingerprint(vibesort)
    st.session_state["taste_fingerprint_key"] = _fp_cache_key

fp = st.session_state["taste_fingerprint"]

tab_mine, tab_compare = st.tabs(["My Taste Map", "Compare with Someone"])

# ── TAB 1: My Taste Map ───────────────────────────────────────────────────────
with tab_mine:
    me_name = fp.get("display_name", "You")

    col_h1, col_h2, col_h3, col_h4 = st.columns(4)
    col_h1.metric("Total Tracks", fp["total_tracks"])
    col_h2.metric("Top Genres",   len(fp["genre_dist"]))
    col_h3.metric("Eras",         len(fp["era_dist"]))
    col_h4.metric("Top Artists",  len(fp["top_artists"]))

    st.write("")

    c_genres, c_audio = st.columns(2)

    with c_genres:
        st.markdown("#### Genre Distribution")
        st.caption("Non-exclusive membership share (one track can contribute to multiple genres).")
        if fp["genre_dist"]:
            try:
                import pandas as pd
                gd = fp["genre_dist"]
                df = pd.DataFrame({
                    "Genre": list(gd.keys()),
                    "Share": [round(v * 100, 1) for v in gd.values()],
                })
                st.bar_chart(df.set_index("Genre"))
            except Exception:
                for g, v in fp["genre_dist"].items():
                    st.write(f"**{g}** — {round(v*100,1)}%")
        else:
            st.caption("No genre data — rescan to populate.")
        if fp.get("primary_genre_dist"):
            st.markdown("**Primary Genre Split** *(exclusive, one genre per track)*")
            for g, v in fp["primary_genre_dist"].items():
                st.caption(f"{g}: {round(v * 100, 1)}%")

    with c_audio:
        st.markdown("#### Audio Profile")
        ap = fp.get("audio_profile", {})

        # Detect if all values are the neutral 0.5 default
        # (happens when Spotify audio features are blocked in Dev Mode)
        _audio_keys   = ["energy", "valence", "danceability", "acousticness", "instrumentalness"]
        _audio_values = [ap.get(k, 0.5) for k in _audio_keys] if ap else []
        _all_neutral  = ap and all(abs(v - 0.5) < 0.02 for v in _audio_values)

        if ap and not _all_neutral:
            labels = {
                "energy":           "⚡ Energy",
                "valence":          "😊 Positivity",
                "danceability":     "💃 Danceability",
                "tempo_norm":       "⏱ Tempo",
                "acousticness":     "🎸 Acousticness",
                "instrumentalness": "🎹 Instrumentalness",
            }
            for key, label in labels.items():
                val = ap.get(key, 0.5)
                pct = int(val * 100)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                st.markdown(
                    f"<div style='font-family:JetBrains Mono,monospace;font-size:0.82rem;"
                    f"color:#d4c5e2;margin:2px 0'>"
                    f"{label:<22} <span style='color:#c0006a'>{bar}</span>"
                    f" <span style='color:#7a6a8a'>{pct}%</span></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption(
                "⚠️ Spotify audio features unavailable — this endpoint was deprecated "
                "in Nov 2024 and returns 403 in Development Mode."
            )
            st.markdown(
                "Apply for [Extended Quota Mode](https://developer.spotify.com/documentation/"
                "web-api/concepts/quota-modes) to unlock real audio analysis (energy, tempo, "
                "danceability etc.)."
            )

        # ── Lyric mood profile (from Genius) — shown when available ──────────
        scan_flags = vibesort.get("scan_flags", {})
        if scan_flags.get("has_lyrics"):
            track_tags_all = vibesort.get("track_tags", {})
            lyr_totals: dict[str, float] = {}
            lyr_counts: dict[str, int]   = {}
            for uri_tags in track_tags_all.values():
                for k, v in uri_tags.items():
                    if k.startswith("lyr_"):
                        mood = k[4:]
                        lyr_totals[mood] = lyr_totals.get(mood, 0) + v
                        lyr_counts[mood] = lyr_counts.get(mood, 0) + 1
            if lyr_totals:
                st.markdown("**Lyrical mood profile** *(from lyrics analysis)*")
                lyr_labels = {
                    "sad":           "💔 Sad",
                    "dark":          "🖤 Dark",
                    "angry":         "🔥 Angry",
                    "love":          "❤️ Love",
                    "hype":          "⚡ Hype",
                    "introspective": "🌀 Introspective",
                    "euphoric":      "✨ Euphoric",
                    "party":         "🎉 Party",
                    "goodbye":       "👋 Goodbye",
                    "hope":          "🌅 Hope",
                    "faith":         "🙏 Faith",
                    "struggle":      "⚙️ Struggle",
                    "money":         "💵 Money",
                    "family":        "👪 Family",
                    "friends":       "🤝 Friends",
                    "jealousy":      "💢 Jealousy",
                    "summer":        "☀️ Summer",
                    "city":          "🏙 City",
                    "ocean":         "🌊 Ocean",
                }
                # Show lyric theme prevalence as % of library tracks that carry
                # each theme. Cap bars at 50% so no category dominates the display
                # (a category hitting 50%+ of the library is rare and the relative
                # shape matters more than absolute scale).
                _lyr_total_tracks = max(len(track_tags_all), 1)
                _CAP = 0.50  # 50% of library = full bar
                for mood_key, label in lyr_labels.items():
                    if mood_key not in lyr_counts:
                        continue
                    # % of library tracks that carry this lyric theme (count-based)
                    prevalence = lyr_counts[mood_key] / _lyr_total_tracks
                    pct = int(prevalence * 100)  # real % of library
                    bar_fill = min(prevalence / _CAP, 1.0)  # normalise to 50% cap
                    bar = "█" * int(bar_fill * 20) + "░" * (20 - int(bar_fill * 20))
                    st.markdown(
                        f"<div style='font-family:JetBrains Mono,monospace;font-size:0.78rem;"
                        f"color:#d4c5e2;margin:2px 0'>"
                        f"{label:<22} <span style='color:#8b000099'>{bar}</span>"
                        f" <span style='color:#7a6a8a'>{pct}%</span></div>",
                        unsafe_allow_html=True,
                    )

    st.write("")

    c_era, c_tags = st.columns(2)

    with c_era:
        st.markdown("#### Era Distribution")
        if fp["era_dist"]:
            try:
                import pandas as pd
                ed = dict(sorted(fp["era_dist"].items()))
                df = pd.DataFrame({
                    "Era": list(ed.keys()),
                    "Share": [round(v * 100, 1) for v in ed.values()],
                })
                st.bar_chart(df.set_index("Era"))
            except Exception:
                for e, v in fp["era_dist"].items():
                    st.write(f"**{e}** — {round(v*100,1)}%")
        else:
            st.caption("No era data.")

    with c_tags:
        st.markdown("#### Taste Tags")
        st.caption("Pattern tags from playlist/mining context (lyrics tags shown separately).")
        tags = fp.get("taste_tags", {})
        if tags:
            top_tags = list(tags.items())[:20]
            max_w = max(w for _, w in top_tags) if top_tags else 1
            html = "<div style='display:flex;flex-wrap:wrap;gap:6px;margin-top:8px'>"
            for tag, w in top_tags:
                # Normalise display: underscores → spaces, title-case
                display_tag = tag.replace("_", " ").title()
                opacity = 0.45 + 0.55 * (w / max_w)
                html += (
                    f"<span style='background:#3d0050;color:#c0006a;"
                    f"padding:3px 10px;border-radius:12px;"
                    f"font-family:JetBrains Mono,monospace;font-size:0.78rem;"
                    f"opacity:{opacity:.2f};border:1px solid #8b000066'>{display_tag}</span>"
                )
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.caption("No tags yet — run a scan with fresh playlist mining.")
        lyrical = fp.get("lyrical_tags", {})
        if lyrical:
            st.markdown("**Lyrical Themes**")
            st.caption("Derived from lyrics analysis (`lyr_*` features).")
            st.caption(" · ".join([f"{k} ({int(v)})" for k, v in list(lyrical.items())[:8]]))

    st.write("")
    st.markdown("#### Top Artists")
    if fp["top_artists"]:
        cols = st.columns(4)
        for i, a in enumerate(fp["top_artists"][:16]):
            with cols[i % 4]:
                genres_str = ", ".join(a["genres"][:2]) if a["genres"] else "—"
                st.markdown(
                    f"<div style='background:#0e000e;border:1px solid #320044;"
                    f"border-radius:6px;padding:8px 10px;margin-bottom:6px'>"
                    f"<div style='color:#c0006a;font-family:Cinzel,serif;font-size:0.82rem'>{a['name']}</div>"
                    f"<div style='color:#7a6a8a;font-family:JetBrains Mono,monospace;font-size:0.72rem'>"
                    f"{a['tracks']} tracks · {genres_str}</div></div>",
                    unsafe_allow_html=True,
                )

    st.write("")
    st.divider()

    # Export
    st.markdown("#### Export Your Fingerprint")
    st.write(
        "Share this file with someone. They paste it into the **Compare** tab "
        "to see taste compatibility, shared artists, genre overlap, and more."
    )
    fp_json = json.dumps(fp, indent=2)
    col_dl, col_copy = st.columns([2, 3])
    with col_dl:
        st.download_button(
            "Download taste_map.json",
            data=fp_json,
            file_name="taste_map.json",
            mime="application/json",
            use_container_width=True,
            type="primary",
        )
    with col_copy:
        st.code(f"// {fp['display_name']} · {fp['total_tracks']} tracks · "
                f"{len(fp['genre_dist'])} genres · exported {fp['exported_at'][:10]}")


# ── TAB 2: Compare ────────────────────────────────────────────────────────────
with tab_compare:
    st.markdown("#### Paste or upload a friend's Taste Map")
    st.write("They export their file from the **My Taste Map** tab and send it to you.")

    col_up, col_paste = st.columns([1, 2])

    their_fp = None

    with col_up:
        uploaded = st.file_uploader("Upload taste_map.json", type=["json"])
        if uploaded:
            try:
                their_fp = json.loads(uploaded.read())
                st.success(f"Loaded: {their_fp.get('display_name', 'Unknown')}")
            except Exception as e:
                st.error(f"Invalid file: {e}")

    with col_paste:
        raw = st.text_area(
            "Or paste JSON directly",
            height=120,
            placeholder='{"version": 2, "display_name": "...", ...}',
        )
        if raw.strip() and not their_fp:
            try:
                their_fp = json.loads(raw.strip())
                st.success(f"Loaded: {their_fp.get('display_name', 'Unknown')}")
            except Exception:
                st.error("Couldn't parse JSON — make sure it's a valid taste_map.json.")

    if their_fp:
        their_name = their_fp.get("display_name", "Them")
        my_name    = fp.get("display_name", "You")

        compat = _compat_score(fp, their_fp)
        overall_pct = int(compat["overall"] * 100)

        st.divider()

        # Overall score
        score_color = "#2d6a2d" if overall_pct >= 60 else ("#8b6000" if overall_pct >= 35 else "#8b0000")
        st.markdown(
            f"<div style='text-align:center;padding:20px 0'>"
            f"<div style='font-family:Cinzel,serif;font-size:3rem;color:{score_color};"
            f"text-shadow:0 0 20px {score_color}88'>{overall_pct}%</div>"
            f"<div style='font-family:JetBrains Mono,monospace;color:#7a6a8a;font-size:0.9rem'>"
            f"taste compatibility · {my_name} × {their_name}</div></div>",
            unsafe_allow_html=True,
        )

        # Score breakdown
        st.markdown("#### Breakdown")
        breakdown = [
            ("Genre overlap",   compat["genre_score"],   "How much your genre taste aligns"),
            ("Artist overlap",  compat["artist_score"],  "Artists you both listen to"),
            ("Mood overlap",    compat["mood_score"],     "Shared emotional zones"),
            ("Vibe tags",       compat["tag_score"],      "Shared playlist context tags"),
            ("Audio similarity",compat["audio_score"],   "Similar energy/valence/danceability profile"),
        ]
        for label, score, hint in breakdown:
            pct = int(score * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            st.markdown(
                f"<div style='font-family:JetBrains Mono,monospace;font-size:0.82rem;"
                f"color:#d4c5e2;margin:3px 0'>"
                f"<span style='color:#7a6a8a'>{label:<20}</span> "
                f"<span style='color:#c0006a'>{bar}</span> "
                f"<span style='color:#7a6a8a'>{pct}%</span>"
                f"<span style='color:#3d0050;font-size:0.72rem'> · {hint}</span></div>",
                unsafe_allow_html=True,
            )

        st.write("")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("#### Common Artists")
            common_artists = compat["common_artists"]
            if common_artists:
                for a in common_artists[:10]:
                    st.markdown(
                        f"<div style='color:#c0006a;font-family:JetBrains Mono,monospace;"
                        f"font-size:0.82rem;padding:2px 0'>✦ {a}</div>",
                        unsafe_allow_html=True,
                    )
                if len(common_artists) > 10:
                    st.caption(f"+{len(common_artists)-10} more")
            else:
                st.caption("No overlap in top artists.")

        with c2:
            st.markdown("#### Common Genres")
            for g in compat["common_genres"][:8]:
                st.markdown(
                    f"<div style='color:#d4c5e2;font-family:JetBrains Mono,monospace;"
                    f"font-size:0.82rem;padding:2px 0'>• {g}</div>",
                    unsafe_allow_html=True,
                )
            if compat["your_unique"]:
                st.write("")
                st.markdown(f"<div style='color:#7a6a8a;font-size:0.78rem'>Only you: "
                             f"{', '.join(compat['your_unique'][:4])}</div>",
                             unsafe_allow_html=True)
            if compat["their_unique"]:
                st.markdown(f"<div style='color:#7a6a8a;font-size:0.78rem'>Only {their_name}: "
                             f"{', '.join(compat['their_unique'][:4])}</div>",
                             unsafe_allow_html=True)

        with c3:
            st.markdown("#### Common Moods")
            for m in compat["common_moods"][:8]:
                st.markdown(
                    f"<div style='color:#d4c5e2;font-family:JetBrains Mono,monospace;"
                    f"font-size:0.82rem;padding:2px 0'>◈ {m}</div>",
                    unsafe_allow_html=True,
                )
            if not compat["common_moods"]:
                st.caption("No shared moods — very different emotional zones.")

        if compat["common_tags"]:
            st.write("")
            st.markdown("#### Shared Taste Tags")
            html = "<div style='display:flex;flex-wrap:wrap;gap:6px'>"
            for tag in compat["common_tags"]:
                display_tag = tag.replace("_", " ").title()
                html += (
                    f"<span style='background:#1a0020;color:#c0006a;"
                    f"padding:3px 10px;border-radius:12px;"
                    f"font-family:JetBrains Mono,monospace;font-size:0.78rem;"
                    f"border:1px solid #c0006a44'>{display_tag}</span>"
                )
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

    else:
        st.info("Upload or paste a taste_map.json to see compatibility.")
