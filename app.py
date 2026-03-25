"""
app.py — Vibesort main entry point.
Run with: python launch.py
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
        "Get help": "https://github.com/PapaKoftes/VibeSort",
        "Report a bug": "https://github.com/PapaKoftes/VibeSort/issues",
        "About": (
            "## Vibesort\n"
            "**Your Spotify library, sorted by feeling.**\n\n"
            "Scans your liked songs and automatically builds mood, genre, era, "
            "and artist playlists using a multi-signal scoring engine — "
            "audio features + playlist mining + genre hierarchy.\n\n"
            "40 mood presets · 42-genre hierarchy · staging shelf · batch deploy\n\n"
            "Open source · [github.com/PapaKoftes/VibeSort](https://github.com/PapaKoftes/VibeSort)"
        ),
    },
)

from core.theme import inject
inject()

# Redirect to connect if not authenticated
if "spotify_token" not in st.session_state:
    st.switch_page("pages/1_Connect.py")
else:
    st.switch_page("pages/3_Vibes.py")
