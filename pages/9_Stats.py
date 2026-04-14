"""
pages/8_Stats.py — Taste report and stats dashboard.
"""
import os
import sys
import collections

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

vibesort         = st.session_state["vibesort"]
all_tracks       = vibesort.get("all_tracks", [])
profiles         = vibesort.get("profiles", {})
genre_map        = vibesort.get("genre_map", {})
era_map          = vibesort.get("era_map", {})
artist_map       = vibesort.get("artist_map", {})
mood_results     = vibesort.get("mood_results", {})
audio_features   = vibesort.get("audio_features", {})
history_stats    = vibesort.get("history_stats", {})
user_mean        = vibesort.get("user_mean", [0.5] * 6)
top_artists_list = vibesort.get("top_artists", [])
user_tag_prefs   = vibesort.get("user_tag_prefs", {})
track_tags       = vibesort.get("track_tags", {}) or {}
artist_genres    = vibesort.get("artist_genres", {}) or {}
scan_flags       = vibesort.get("scan_flags", {}) or {}
lyrics_lang_map  = vibesort.get("lyrics_language_map") or {}
top_tracks_list  = vibesort.get("top_tracks", [])
artist_popularity = vibesort.get("artist_popularity") or {}

try:
    import pandas as pd
    _has_pd = True
except Exception:
    _has_pd = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def avg_feature(key):
    vals = [f.get(key, 0) for f in audio_features.values() if f]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def _bar(data: dict, label: str, color: str = "#c0006a", height: int = 300):
    """Render a bar chart from a {label: value} dict using st.bar_chart."""
    if not data or not _has_pd:
        for k, v in list(data.items())[:10]:
            st.write(f"**{k}** — {v}")
        return
    df = pd.DataFrame({label: list(data.values())}, index=list(data.keys()))
    st.bar_chart(df, color=color, height=height)


def _primary_artist_id(track: dict) -> str:
    arts = track.get("artists") or []
    if not arts:
        return ""
    a0 = arts[0]
    return a0.get("id", "") if isinstance(a0, dict) else ""


def taste_profile_line() -> str:
    top_genres = sorted(genre_map.items(), key=lambda x: -len(x[1]))[:2]
    top_genre_names = [g for g, _ in top_genres if g != "Other"]
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
pops = [t.get("popularity", 50) for t in all_tracks if t.get("popularity") is not None]
avg_pop = sum(pops) / len(pops) if pops else 50
obscurity = round(100 - avg_pop, 1)
obscurity_label = (
    "deep underground" if obscurity >= 65 else
    "leaning underground" if obscurity >= 45 else
    "balanced" if obscurity >= 30 else
    "mostly mainstream"
)

unique_artists = len({
    a.get("id", a) if isinstance(a, dict) else a
    for t in all_tracks
    for a in (t.get("artists") or [])
    if a
})

# top moods computed once
top_moods = sorted(mood_results.items(), key=lambda x: -x[1].get("count", 0))[:10]

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Tracks", f"{len(all_tracks):,}")
m2.metric("Unique Artists", f"{unique_artists:,}")
m3.metric("Genres", len(genre_map))
m4.metric("Eras", len(era_map))
m5.metric("Moods detected", len(mood_results))
m6.metric(f"Obscurity", f"{obscurity}/100", help=obscurity_label)

_ah_sum, _ah_n = 0, 0
for _t in all_tracks:
    _pid = (_t.get("artists") or [{}])[0].get("id")
    if _pid and _pid in artist_popularity:
        _ah_sum += int(artist_popularity[_pid])
        _ah_n += 1
if _ah_n:
    st.caption(
        f"Average artist popularity: **{round(_ah_sum / _ah_n, 1)}/100** "
        f"(Spotify score, lower = smaller acts) · "
        f"Obscurity index: **{obscurity}/100** ({obscurity_label})"
    )

st.divider()

# ── Taste Profile ─────────────────────────────────────────────────────────────
st.subheader("Taste Profile")
st.info(taste_profile_line())

st.divider()

# ── Genre breakdown ───────────────────────────────────────────────────────────
st.subheader("Genre Breakdown")
_top_genres = sorted(genre_map.items(), key=lambda x: -len(x[1]))
if _top_genres:
    _g_data = {g: len(uris) for g, uris in _top_genres[:15]}
    _bar(_g_data, "Tracks", color="#c0006a")
    st.caption(
        f"{len(_top_genres)} genre buckets total · "
        f"{'Other: ' + str(len(genre_map.get('Other', []))) + ' tracks · ' if 'Other' in genre_map else ''}"
        f"A track can appear in multiple genres."
    )

# Genre mix (multi-affiliation)
with st.expander("Genre affinity — weighted library share"):
    _multi: dict[str, float] = {}
    for _p in profiles.values():
        _macros = [g for g in (_p.get("macro_genres") or []) if g != "Other"]
        if not _macros:
            continue
        _w = 1.0 / len(_macros)
        for _g in _macros:
            _multi[_g] = _multi.get(_g, 0.0) + _w
    _multi_sorted = sorted(_multi.items(), key=lambda x: -x[1])[:15]
    _n_prof = max(len(profiles), 1)
    if _multi_sorted:
        _bar(
            {g: round(100 * w / _n_prof, 1) for g, w in _multi_sorted},
            "Library affinity %",
            color="#8b0000",
        )
        st.caption(
            "Each track splits one vote across all its macro genres — "
            "percentages add up to more than 100%."
        )

st.divider()

# ── Era distribution ──────────────────────────────────────────────────────────
st.subheader("Era Distribution")
sorted_eras = sorted(era_map.items(), key=lambda x: x[0])
if sorted_eras:
    _bar({e: len(uris) for e, uris in sorted_eras}, "Tracks", color="#3d0050", height=250)

# Era vs genre cross-tab
if sorted_eras and _top_genres:
    with st.expander("Era breakdown — which eras your top genres dominate"):
        _top3_genres = [g for g, _ in _top_genres[:3] if g != "Other"]
        if _top3_genres and _has_pd:
            _uri_to_year: dict[str, str] = {}
            for _t in all_tracks:
                _u = _t.get("uri", "")
                _y = _t.get("album", {}).get("release_date", "")[:4] if _t.get("album") else ""
                if _u and _y and _y.isdigit():
                    _decade = str((int(_y) // 10) * 10) + "s"
                    _uri_to_year[_u] = _decade
            _cross: dict[str, dict[str, int]] = {g: {} for g in _top3_genres}
            for _g in _top3_genres:
                for _u in genre_map.get(_g, []):
                    _dec = _uri_to_year.get(_u)
                    if _dec:
                        _cross[_g][_dec] = _cross[_g].get(_dec, 0) + 1
            _decades = sorted({d for c in _cross.values() for d in c})
            _rows = []
            for _dec in _decades:
                _row = {"Era": _dec}
                for _g in _top3_genres:
                    _row[_g] = _cross[_g].get(_dec, 0)
                _rows.append(_row)
            if _rows:
                df_cross = pd.DataFrame(_rows).set_index("Era")
                st.bar_chart(df_cross, height=220)

st.divider()

# ── Mood breakdown ────────────────────────────────────────────────────────────
st.subheader("Mood Detection")
if mood_results:
    _mood_by_count = sorted(mood_results.items(), key=lambda x: -x[1].get("count", 0))
    _bar(
        {name: info.get("count", 0) for name, info in _mood_by_count[:20]},
        "Tracks",
        color="#c0006a",
        height=350,
    )
    # Cohesion sub-chart
    with st.expander("Mood cohesion scores — how tightly each playlist clusters"):
        _bar(
            {name: round(info.get("cohesion", 0) * 100, 1) for name, info in
             sorted(mood_results.items(), key=lambda x: -x[1].get("cohesion", 0))[:20]},
            "Cohesion %",
            color="#3d0050",
            height=300,
        )
        st.caption("100% = perfectly tight. 60%+ is strong. Below 50% = loose but usable.")

st.divider()

# ── Audio fingerprint ─────────────────────────────────────────────────────────
st.subheader("Audio Fingerprint")
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
    energy       = user_mean[0] if len(user_mean) > 0 else 0.5
    valence      = user_mean[1] if len(user_mean) > 1 else 0.5
    danceability = user_mean[2] if len(user_mean) > 2 else 0.5
    acousticness = user_mean[4] if len(user_mean) > 4 else 0.5
    instrumental = user_mean[5] if len(user_mean) > 5 else 0.0
    avg_tempo    = 0
    _fp_source   = "*(estimated from track profiles — Spotify audio endpoint deprecated)*"

fp_cols = st.columns(5)
fp_cols[0].metric("Energy",       f"{energy:.2f}")
fp_cols[1].metric("Valence",      f"{valence:.2f}")
fp_cols[2].metric("Danceability", f"{danceability:.2f}")
fp_cols[3].metric("Acousticness", f"{acousticness:.2f}")
fp_cols[4].metric("Instrumental", f"{instrumental:.2f}")
if avg_tempo:
    st.caption(f"Average tempo: {avg_tempo} BPM")
if _fp_source:
    st.caption(_fp_source)

st.divider()

# ── Top artists ───────────────────────────────────────────────────────────────
st.subheader("Top Artists by Track Count")
_top_artists_by_count = sorted(artist_map.items(), key=lambda x: -len(x[1]))[:15]
if _top_artists_by_count:
    _bar(
        {a: len(uris) for a, uris in _top_artists_by_count},
        "Tracks",
        color="#8b0000",
        height=300,
    )

# Also show Spotify's own top artists if available
if top_artists_list:
    with st.expander(f"Your Spotify top artists ({len(top_artists_list)} across all time ranges)"):
        _sp_top = [(a.get("name", "?"), a.get("popularity", 0)) for a in top_artists_list[:20]]
        if _sp_top and _has_pd:
            _bar(
                {name: pop for name, pop in _sp_top},
                "Spotify Popularity",
                color="#3d0050",
                height=280,
            )

st.divider()

# ── Vibe tags ─────────────────────────────────────────────────────────────────
st.subheader("Vibe Tags")
st.caption("Your library's most-associated mood and context words from all enrichment sources.")
if user_tag_prefs:
    # Tag cloud
    top_tags = sorted(user_tag_prefs.items(), key=lambda x: -x[1])[:40]
    max_w = max(w for _, w in top_tags) if top_tags else 1
    html = "<div style='display:flex;flex-wrap:wrap;gap:6px;margin-top:4px'>"
    for tag, w in top_tags:
        opacity = 0.35 + 0.65 * (w / max_w)
        size = 0.72 + 0.28 * (w / max_w)
        html += (
            f"<span style='background:#1a0020;color:#c0006a;"
            f"padding:4px 11px;border-radius:14px;"
            f"font-family:JetBrains Mono,monospace;font-size:{size:.2f}rem;"
            f"opacity:{opacity:.2f};border:1px solid #c0006a44'>{tag}</span>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
    st.write("")

    # Bar chart of top 20 tags
    with st.expander("Tag frequency — top 20"):
        _bar(
            {t: round(w, 3) for t, w in top_tags[:20]},
            "Tag weight",
            color="#c0006a",
            height=280,
        )
else:
    st.caption("No vibe tags yet — connect Last.fm and re-scan for rich mood tagging.")

st.divider()

# ── Lyrics language ───────────────────────────────────────────────────────────
if lyrics_lang_map:
    st.subheader("Lyrics Languages")
    st.caption("Languages detected in your library's lyrics.")
    _lang_counts = collections.Counter(lyrics_lang_map.values())
    _lang_sorted = sorted(_lang_counts.items(), key=lambda x: -x[1])
    _total_lang = sum(_lang_counts.values())
    _bar(
        {lang: count for lang, count in _lang_sorted[:15]},
        "Tracks",
        color="#3d0050",
        height=250,
    )
    st.caption(
        f"{_total_lang} tracks with detected lyrics · "
        f"{len(_lang_sorted)} languages · "
        f"top: {_lang_sorted[0][0]} ({_lang_sorted[0][1]} tracks)" if _lang_sorted else ""
    )
    st.divider()

# ── Enrichment coverage ───────────────────────────────────────────────────────
st.subheader("Enrichment Coverage")
st.caption("How much of your library received useful signals from each data layer.")

_n_total = max(len(all_tracks), 1)
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
    has_genre = bool(artist_genres.get(aid, []) if aid else [])
    tags = track_tags.get(uri) or {}
    lyr_keys   = [k for k in tags if str(k).lower().startswith("lyr_")]
    other_keys = [k for k in tags if not str(k).lower().startswith("lyr_")]
    has_lyr    = bool(lyr_keys)
    has_other  = bool(other_keys)

    if has_genre:
        _n_genre += 1
    if has_lyr:
        _n_lyr += 1
    if has_other:
        _n_non_lyr_tags += 1
    if has_genre and not has_other:
        _n_genre_only += 1
    if not has_genre and not bool(tags):
        _n_blank += 1

cov_cols = st.columns(4)
cov_cols[0].metric("Genres", f"{_n_genre:,}", f"{round(100*_n_genre/_n_total)}%")
cov_cols[1].metric("Mood tags", f"{_n_non_lyr_tags:,}", f"{round(100*_n_non_lyr_tags/_n_total)}%")
cov_cols[2].metric("Lyrics", f"{_n_lyr:,}", f"{round(100*_n_lyr/_n_total)}%")
cov_cols[3].metric("No data", f"{_n_blank:,}", f"{round(100*_n_blank/_n_total)}%")

if _has_pd:
    _cov_data = {
        "Genres (Spotify/Deezer/enrichers)": _n_genre,
        "Mood tags (Last.fm/AudioDB/Discogs)": _n_non_lyr_tags,
        "Lyrics-derived": _n_lyr,
    }
    _bar(_cov_data, "Tracks covered", color="#8b0000", height=220)

if scan_flags:
    st.caption(
        "Scan flags · "
        f"tags: {'✅' if scan_flags.get('has_tags') else '❌'}  "
        f"genres: {'✅' if scan_flags.get('has_genres') else '❌'}  "
        f"lyrics: {'✅' if scan_flags.get('has_lyrics') else '❌'}  "
        f"discogs: {'✅' if scan_flags.get('has_discogs') else '❌'}  "
        f"genius: {'✅' if scan_flags.get('has_genius') else '❌'}  "
        f"listenbrainz: {'✅' if scan_flags.get('has_listenbrainz') else '❌'}"
    )

st.divider()

# ── History stats ─────────────────────────────────────────────────────────────
if history_stats:
    st.subheader("Spotify History Export")
    hs = history_stats
    h1, h2, h3 = st.columns(3)
    h1.metric("Total Streams", hs.get("total_streams", "—"))
    h2.metric("Hours Listened", hs.get("total_hours", "—"))
    h3.metric("Listening Since", hs.get("earliest", "—"))
    st.divider()

# ── Export ────────────────────────────────────────────────────────────────────
if st.button("Export Taste Report as .txt", use_container_width=False):
    try:
        os.makedirs("outputs", exist_ok=True)
        top_genre = max(genre_map.items(), key=lambda x: len(x[1]), default=("?", []))
        top_era   = max(era_map.items(), key=lambda x: len(x[1]), default=("?", []))
        lines = [
            "VIBESORT — TASTE REPORT",
            "=" * 50,
            f"Library: {len(all_tracks)} tracks across {unique_artists} artists",
            f"Genres: {len(genre_map)} · Eras: {len(era_map)} · Moods: {len(mood_results)}",
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
        ]
        if avg_tempo:
            lines.append(f"Tempo avg:     {avg_tempo} BPM")
        lines += ["", "TOP GENRES"]
        for g, uris in _top_genres[:10]:
            lines.append(f"  {g}: {len(uris)} tracks")
        lines += ["", "TOP MOODS (by track count)"]
        for name, info in _mood_by_count[:10]:
            lines.append(f"  {name}: {info['count']} tracks ({info.get('cohesion',0)*100:.0f}% cohesion)")
        lines += ["", f"Taste: {taste_profile_line()}"]
        report_path = os.path.join("outputs", "taste_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        st.success(f"Saved to {os.path.abspath(report_path)}")
    except Exception as e:
        st.error(f"Could not export: {e}")
