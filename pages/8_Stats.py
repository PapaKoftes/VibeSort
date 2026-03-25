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
from core.theme import inject
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def avg_feature(key):
    vals = [f.get(key, 0) for f in audio_features.values() if f]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def taste_profile_line() -> str:
    """Generate a one-line personality description from top genres and audio."""
    top_genres = sorted(genre_map.items(), key=lambda x: -len(x[1]))[:2]
    top_genre_names = [g for g, _ in top_genres]

    energy    = avg_feature("energy")
    valence   = avg_feature("valence")
    acoustic  = avg_feature("acousticness")

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

st.divider()

# ── Taste profile ─────────────────────────────────────────────────────────────
st.subheader("Taste Profile")
st.info(taste_profile_line())

st.divider()

# ── Audio fingerprint ─────────────────────────────────────────────────────────
st.subheader("Audio Fingerprint")

energy       = avg_feature("energy")
valence      = avg_feature("valence")
danceability = avg_feature("danceability")
acousticness = avg_feature("acousticness")
instrumental = avg_feature("instrumentalness")
tempos       = [f.get("tempo", 120) for f in audio_features.values() if f]
avg_tempo    = round(sum(tempos) / len(tempos)) if tempos else 0

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
