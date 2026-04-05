"""
pages/8_Stats.py — Taste report and stats dashboard.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Vibesort — Stats",
    page_icon="🎧",
    layout="wide",
)
from core.theme import inject, render_scan_quality_strip
inject()

if not st.session_state.get("spotify_token"):
    st.warning("Please connect to Spotify first.")
    if st.button("Connect"):
        st.switch_page("pages/1_Connect.py")
    st.stop()

if not st.session_state.get("vibesort"):
    st.info("Scan your library to see your stats.")
    if st.button("Scan Library"):
        st.switch_page("pages/2_Scan.py")
    st.stop()

vibesort = st.session_state["vibesort"]
all_tracks     = vibesort.get("all_tracks", [])
profiles       = vibesort.get("profiles", {})
genre_map      = vibesort.get("genre_map", {})
era_map        = vibesort.get("era_map", {})
artist_map     = vibesort.get("artist_map", {})
mood_results   = vibesort.get("mood_results", {})
audio_features = vibesort.get("audio_features", {})
history_stats  = vibesort.get("history_stats", {})
user_mean      = vibesort.get("user_mean", [0.5] * 6)
top_artists_list = vibesort.get("top_artists", [])
user_tag_prefs   = vibesort.get("user_tag_prefs", {})
track_tags     = vibesort.get("track_tags", {}) or {}
artist_genres  = vibesort.get("artist_genres", {}) or {}
scan_flags     = vibesort.get("scan_flags", {}) or {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def avg_feature(key):
    vals = [f.get(key, 0) for f in audio_features.values() if f]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def taste_profile_line() -> str:
    """Generate a one-line personality description from top genres and audio."""
    top_genres = sorted(genre_map.items(), key=lambda x: -len(x[1]))[:2]
    top_genre_names = [g for g, _ in top_genres if g != "Other"]

    # audio_features may be empty (Spotify deprecated the endpoint Nov 2024).
    # Fall back to user_mean from track profiles — same values, always available.
    if audio_features:
        energy   = avg_feature("energy")
        valence  = avg_feature("valence")
        acoustic = avg_feature("acousticness")
    else:
        energy   = user_mean[0] if len(user_mean) > 0 else 0.5
        valence  = user_mean[1] if len(user_mean) > 1 else 0.5
        acoustic = user_mean[4] if len(user_mean) > 4 else 0.5

    if energy >= 0.75 and valence < 0.35:
        energy_word = "dark, high-energy"
    elif energy >= 0.70:
        energy_word = "high-energy"
    elif energy < 0.35 and valence < 0.40:
        energy_word = "melancholic"
    elif energy < 0.40:
        energy_word = "low-key"
    elif acoustic > 0.60:
        energy_word = "acoustic and introspective"
    elif valence > 0.70:
        energy_word = "upbeat"
    else:
        energy_word = "balanced"

    genres_str = " and ".join(top_genre_names) if top_genre_names else "a wide variety of music"
    pops = [t.get("popularity", 50) for t in all_tracks if t.get("popularity") is not None]
    avg_pop = sum(pops) / len(pops) if pops else 50
    if avg_pop < 35:
        pop_word = "mostly underground artists"
    elif avg_pop < 55:
        pop_word = "a mix of underground and mainstream"
    else:
        pop_word = "mostly mainstream artists"

    return (
        f"You listen to a lot of {energy_word} music — mostly {genres_str}. "
        f"Your taste leans toward {pop_word}."
    )


# ── Page ─────────────────────────────────────────────────────────────────────

st.title("Your Taste Report")
render_scan_quality_strip(vibesort)
st.write("")

# ── Overview metrics ──────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
pops = [t.get("popularity", 50) for t in all_tracks if t.get("popularity") is not None]
avg_pop = sum(pops) / len(pops) if pops else 50
obscurity = round(100 - avg_pop, 1)
obscurity_label = (
    "deep underground" if obscurity >= 65 else
    "leaning underground" if obscurity >= 45 else
    "balanced" if obscurity >= 30 else
    "mostly mainstream"
)

col1.metric("Tracks", len(all_tracks))
col2.metric("Genres", len(genre_map))
col3.metric("Eras", len(era_map))
col4.metric(f"Obscurity ({obscurity_label})", f"{obscurity}/100")

_apop = vibesort.get("artist_popularity") or {}
_ah_sum, _ah_n = 0, 0
for _t in all_tracks:
    _arts = _t.get("artists") or []
    if _arts and isinstance(_arts[0], dict):
        _pid = _arts[0].get("id")
        if _pid and _pid in _apop:
            _ah_sum += int(_apop[_pid])
            _ah_n += 1
if _ah_n:
    _ah = round(_ah_sum / _ah_n, 1)
    st.caption(
        f"**Artist heat (Spotify):** average primary-artist popularity **{_ah}/100** "
        f"across {_ah_n} tracks — complements track obscurity (lower = typically smaller acts)."
    )
else:
    st.caption(
        "**Artist heat:** rescans fetch Spotify artist popularity (0–100) for niche-vs-mainstream context."
    )

st.divider()

# ── Enrichment coverage ───────────────────────────────────────────────────────
st.subheader("Enrichment coverage")
st.caption(
    "How much of your library received signals from genres, tags, and lyrics. "
    "Tag sources (Last.fm, AudioDB, Discogs, mining) are merged in one layer."
)

_n_total = len(all_tracks)


def _primary_artist_id(track: dict) -> str:
    arts = track.get("artists") or []
    if not arts:
        return ""
    a0 = arts[0]
    return a0.get("id", "") if isinstance(a0, dict) else ""


_n_genre = 0
_n_lyr = 0
_n_non_lyr_tags = 0
_n_genre_only = 0
_n_blank = 0

for t in all_tracks:
    uri = t.get("uri", "")
    if not uri:
        continue
    aid = _primary_artist_id(t)
    genres = artist_genres.get(aid, []) if aid else []
    has_genre = bool(genres)
    tags = track_tags.get(uri) or {}
    lyr_keys = [k for k in tags if str(k).lower().startswith("lyr_")]
    other_keys = [k for k in tags if not str(k).lower().startswith("lyr_")]
    has_lyr = bool(lyr_keys)
    has_other = bool(other_keys)
    has_any_tags = bool(tags)

    if has_genre:
        _n_genre += 1
    if has_lyr:
        _n_lyr += 1
    if has_other:
        _n_non_lyr_tags += 1
    if has_genre and not has_other:
        _n_genre_only += 1
    if not has_genre and not has_any_tags:
        _n_blank += 1

ec1, ec2, ec3, ec4 = st.columns(4)
ec1.metric("Tracks scanned", _n_total)
ec2.metric("With artist genres", _n_genre)
ec3.metric("With mood / context tags", _n_non_lyr_tags)
ec4.metric("With lyric mood scores", _n_lyr)

st.caption(
    f"**Genre only (no context tags):** {_n_genre_only} tracks · "
    f"**No genre & no tags:** {_n_blank} tracks"
)

_cov_rows = [
    {"Source": "Genres (Spotify + Deezer + enrichers)", "Tracks": _n_genre},
    {"Source": "Tags (Last.fm, AudioDB, Discogs, mining, …)", "Tracks": _n_non_lyr_tags},
    {"Source": "Lyrics-derived (lyr_*)", "Tracks": _n_lyr},
]
try:
    import pandas as pd

    st.bar_chart(pd.DataFrame(_cov_rows).set_index("Source"))
except Exception:
    for row in _cov_rows:
        st.write(f"**{row['Source']}** — {row['Tracks']} tracks")

if scan_flags:
    st.caption(
        "Last scan flags: "
        f"tags={scan_flags.get('has_tags')}, genres={scan_flags.get('has_genres')}, "
        f"lyrics={scan_flags.get('has_lyrics')}, discogs_ok={scan_flags.get('has_discogs')}, "
        f"genius_key={scan_flags.get('has_genius')}, listenbrainz={scan_flags.get('has_listenbrainz')}"
    )

st.divider()

# ── Taste profile ─────────────────────────────────────────────────────────────
st.subheader("Taste Profile")
st.info(taste_profile_line())

st.divider()

# ── Audio fingerprint ─────────────────────────────────────────────────────────
st.subheader("Audio Fingerprint")

# audio_features is empty when Spotify's deprecated endpoint returns 403.
# Fall back to user_mean (profile-averaged audio vector) so the chart isn't
# all zeros. user_mean = [energy, valence, danceability, tempo_norm,
#                          acousticness, instrumentalness]
if audio_features:
    energy       = avg_feature("energy")
    valence      = avg_feature("valence")
    danceability = avg_feature("danceability")
    acousticness = avg_feature("acousticness")
    instrumental = avg_feature("instrumentalness")
    tempos       = [f.get("tempo", 120) for f in audio_features.values() if f]
    avg_tempo    = round(sum(tempos) / len(tempos)) if tempos else 0
    _fp_source   = ""
else:
    # Derived from profile audio vectors (neutral [0.5]*6 default per track)
    energy       = user_mean[0] if len(user_mean) > 0 else 0.5
    valence      = user_mean[1] if len(user_mean) > 1 else 0.5
    danceability = user_mean[2] if len(user_mean) > 2 else 0.5
    acousticness = user_mean[4] if len(user_mean) > 4 else 0.5
    instrumental = user_mean[5] if len(user_mean) > 5 else 0.0
    avg_tempo    = 0
    _fp_source   = " *(estimated from track profiles — Spotify audio endpoint deprecated)*"

try:
    import pandas as pd
    fp_data = {
        "Feature": ["Energy", "Valence", "Danceability", "Acousticness", "Instrumental"],
        "Value":   [energy, valence, danceability, acousticness, instrumental],
    }
    df_fp = pd.DataFrame(fp_data).set_index("Feature")
    st.bar_chart(df_fp)
except Exception:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Energy",        f"{energy:.2f}")
    col2.metric("Valence",       f"{valence:.2f}")
    col3.metric("Danceability",  f"{danceability:.2f}")
    col4.metric("Acousticness",  f"{acousticness:.2f}")
    col5.metric("Instrumental",  f"{instrumental:.2f}")

if avg_tempo:
    st.caption(f"Average tempo: {avg_tempo} BPM")
if _fp_source:
    st.caption(_fp_source)

st.divider()

# ── Two-column charts ─────────────────────────────────────────────────────────
left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Top Genres")
    top_genres = sorted(genre_map.items(), key=lambda x: -len(x[1]))[:10]
    if top_genres:
        try:
            import pandas as pd
            df_g = pd.DataFrame(
                {"Tracks": [len(uris) for _, uris in top_genres]},
                index=[g for g, _ in top_genres],
            )
            st.bar_chart(df_g)
        except Exception:
            for g, uris in top_genres[:5]:
                st.write(f"**{g}** — {len(uris)} tracks")
    st.markdown("**Genre mix (multi-affiliation)**")
    st.caption(
        "Each track splits one vote across every macro genre on its artists — "
        "percentages can add up to more than 100% across the library."
    )
    _multi: dict[str, float] = {}
    for _p in profiles.values():
        _macros = [g for g in (_p.get("macro_genres") or []) if g != "Other"]
        if not _macros:
            continue
        _w = 1.0 / len(_macros)
        for _g in _macros:
            _multi[_g] = _multi.get(_g, 0.0) + _w
    _multi_sorted = sorted(_multi.items(), key=lambda x: -x[1])[:12]
    _n_prof = max(len(profiles), 1)
    if _multi_sorted:
        try:
            import pandas as pd
            df_mg = pd.DataFrame(
                {
                    "Library affinity %": [
                        round(100 * w / _n_prof, 2) for _, w in _multi_sorted
                    ]
                },
                index=[g for g, _ in _multi_sorted],
            )
            st.bar_chart(df_mg)
        except Exception:
            for g, w in _multi_sorted[:8]:
                st.caption(f"{g}: {round(100 * w / _n_prof, 1)}% library affinity")

with right_col:
    st.subheader("Top Moods")
    top_moods = sorted(mood_results.items(), key=lambda x: -x[1]["cohesion"])[:10]
    if top_moods:
        try:
            import pandas as pd
            df_m = pd.DataFrame(
                {"Tracks": [info["count"] for _, info in top_moods]},
                index=[name for name, _ in top_moods],
            )
            st.bar_chart(df_m)
        except Exception:
            for name, info in top_moods[:5]:
                st.write(f"**{name}** — {info['count']} tracks ({info['cohesion']*100:.0f}%)")

st.divider()

# ── Era distribution ──────────────────────────────────────────────────────────
st.subheader("Era Distribution")
sorted_eras = sorted(era_map.items(), key=lambda x: x[0])
if sorted_eras:
    try:
        import pandas as pd
        df_e = pd.DataFrame(
            {"Tracks": [len(uris) for _, uris in sorted_eras]},
            index=[e for e, _ in sorted_eras],
        )
        st.bar_chart(df_e)
    except Exception:
        for e, uris in sorted_eras:
            st.write(f"**{e}** — {len(uris)} tracks")

st.divider()

# ── Vibe Tags ─────────────────────────────────────────────────────────────────
# Aggregated from playlist mining or MusicBrainz — shows the mood/genre context
# words most associated with this library.
st.subheader("Vibe Tags")
if user_tag_prefs:
    top_tags = sorted(user_tag_prefs.items(), key=lambda x: -x[1])[:30]
    max_w = max(w for _, w in top_tags) if top_tags else 1
    html = "<div style='display:flex;flex-wrap:wrap;gap:6px;margin-top:4px'>"
    for tag, w in top_tags:
        opacity = 0.40 + 0.60 * (w / max_w)
        html += (
            f"<span style='background:#1a0020;color:#c0006a;"
            f"padding:3px 10px;border-radius:12px;"
            f"font-family:JetBrains Mono,monospace;font-size:0.78rem;"
            f"opacity:{opacity:.2f};border:1px solid #c0006a44'>{tag}</span>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
else:
    st.caption(
        "No vibe tags yet — these appear after a scan with MusicBrainz enrichment "
        "or after Spotify Extended Quota Mode is enabled."
    )

st.divider()

# ── Top artists ───────────────────────────────────────────────────────────────
st.subheader("Top Artists (by track count in library)")
top_artists = sorted(artist_map.items(), key=lambda x: -len(x[1]))[:10]
if top_artists:
    try:
        import pandas as pd
        df_a = pd.DataFrame(
            {"Tracks": [len(uris) for _, uris in top_artists]},
            index=[a for a, _ in top_artists],
        )
        st.bar_chart(df_a)
    except Exception:
        for a, uris in top_artists:
            st.write(f"**{a}** — {len(uris)} tracks")

# ── Last.fm stats ─────────────────────────────────────────────────────────────
try:
    import config as cfg
    has_lastfm = bool(getattr(cfg, "LASTFM_API_KEY", "") and getattr(cfg, "LASTFM_USERNAME", ""))
except Exception:
    has_lastfm = False

if has_lastfm:
    st.divider()
    st.subheader("Last.fm Listening Stats")
    if st.button("Load Last.fm Stats", use_container_width=False):
        with st.spinner("Fetching Last.fm data..."):
            try:
                from core.lastfm import connect as lfm_connect, listening_stats, top_tracks as lfm_top_tracks
                lfm = lfm_connect(cfg.LASTFM_API_KEY, cfg.LASTFM_API_SECRET, cfg.LASTFM_USERNAME)
                if lfm:
                    stats = listening_stats(lfm, cfg.LASTFM_USERNAME)
                    if stats:
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Total Scrobbles", stats.get("playcount", "—"))
                        c2.metric("Tracks Scrobbled", stats.get("track_count", "—"))
                        c3.metric("Artists", stats.get("artist_count", "—"))
                        c4.metric("Albums", stats.get("album_count", "—"))
                else:
                    st.warning("Could not connect to Last.fm. Check your credentials.")
            except Exception as e:
                st.error(f"Last.fm error: {e}")

# ── History stats ─────────────────────────────────────────────────────────────
if history_stats:
    st.divider()
    st.subheader("From Your Spotify History Export")
    hs = history_stats
    h1, h2, h3 = st.columns(3)
    h1.metric("Total Streams", hs.get("total_streams", "—"))
    h2.metric("Hours Listened", hs.get("total_hours", "—"))
    h3.metric("Listening Since", hs.get("earliest", "—"))

st.divider()

# ── Export ────────────────────────────────────────────────────────────────────
if st.button("Export Taste Report", use_container_width=False):
    try:
        os.makedirs("outputs", exist_ok=True)
        top_genre = max(genre_map.items(), key=lambda x: len(x[1]), default=("?", []))
        top_era   = max(era_map.items(), key=lambda x: len(x[1]), default=("?", []))
        lines = [
            "VIBESORT — TASTE REPORT",
            "=" * 50,
            f"Library: {len(all_tracks)} tracks",
            f"Genres: {len(genre_map)}",
            f"Eras: {len(era_map)}",
            f"Obscurity: {obscurity}/100 ({obscurity_label})",
            f"Top genre: {top_genre[0]} ({len(top_genre[1])} tracks)",
            f"Top era: {top_era[0]} ({len(top_era[1])} tracks)",
            "",
            "AUDIO FINGERPRINT",
            f"Energy:        {energy:.3f}",
            f"Valence:       {valence:.3f}",
            f"Danceability:  {danceability:.3f}",
            f"Acousticness:  {acousticness:.3f}",
            f"Instrumental:  {instrumental:.3f}",
            f"Tempo avg:     {avg_tempo} BPM",
            "",
            "TOP GENRES",
        ]
        for g, uris in top_genres:
            lines.append(f"  {g}: {len(uris)} tracks")
        lines += ["", "TOP MOODS"]
        for name, info in top_moods[:5]:
            lines.append(f"  {name}: {info['count']} tracks ({info['cohesion']*100:.0f}% cohesion)")
        lines += ["", f"Taste: {taste_profile_line()}"]

        report_path = os.path.join("outputs", "taste_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        st.success(f"Saved to {os.path.abspath(report_path)}")
    except Exception as e:
        st.error(f"Could not export: {e}")
