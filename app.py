"""
app.py — Vibesort main entry point.
Run with: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Vibesort",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Redirect to connect if not authenticated
if "spotify_token" not in st.session_state:
    st.switch_page("pages/1_Connect.py")
else:
    st.switch_page("pages/3_Vibes.py")
