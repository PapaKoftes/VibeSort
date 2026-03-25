"""
core/theme.py — Vibesort design system.

Call inject() at the top of every Streamlit page.
Applies the dark gothic terminal aesthetic:
  - JetBrains Mono body, Cinzel headings
  - Near-black crimson/violet palette
  - Subtle scanline overlay + breathing title glow
"""

import streamlit as st

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Cinzel:wght@400;600;700;900&display=swap');

/* ── Tokens ──────────────────────────────────────────────────────────────── */
:root {
  --bg:        #0a0008;
  --bg2:       #0e000e;
  --crimson:   #8b0000;
  --violet:    #3d0050;
  --accent:    #c0006a;
  --text:      #d4c5e2;
  --text-dim:  #7a6a8a;
  --code-bg:   #130013;
  --border:    #320044;
  --glow:      #8b000066;
  --asp:       #8b0000;
  --asp-glow:  #8b000044;
}

/* ── Base ────────────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"] {
  background-color: var(--bg) !important;
  color: var(--text) !important;
  font-family: 'JetBrains Mono', 'Courier New', monospace !important;
}

[data-testid="stSidebar"] {
  background-color: var(--bg2) !important;
  border-right: 1px solid var(--border) !important;
}

[data-testid="stHeader"] {
  background-color: var(--bg) !important;
  border-bottom: 1px solid var(--border) !important;
}

/* ── Typography ──────────────────────────────────────────────────────────── */
h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
  font-family: 'Cinzel', Georgia, serif !important;
  color: var(--accent) !important;
  letter-spacing: 0.05em;
  text-shadow: 0 0 12px var(--glow);
  animation: title-breathe 4s ease-in-out infinite;
}

@keyframes title-breathe {
  0%, 100% { text-shadow: 0 0 6px var(--glow); }
  50%       { text-shadow: 0 0 32px var(--accent)55; }
}

p, li, span, label, .stMarkdown p,
[data-testid="stMetricValue"],
[data-testid="stMetricLabel"] {
  font-family: 'JetBrains Mono', monospace !important;
  color: var(--text) !important;
}

.stCaption, small, [data-testid="stCaptionContainer"] {
  color: var(--text-dim) !important;
  font-family: 'JetBrains Mono', monospace !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
[data-testid="stButton"] > button {
  background: transparent !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.82rem !important;
  letter-spacing: 0.04em;
  transition: all 0.2s ease !important;
  border-radius: 3px !important;
}

[data-testid="stButton"] > button:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
  box-shadow: 0 0 10px var(--asp-glow) !important;
  background: #1a000f !important;
}

[data-testid="stButton"] > button[kind="primary"] {
  background: var(--crimson) !important;
  border-color: var(--accent) !important;
  color: #fff !important;
  box-shadow: 0 0 14px var(--glow) !important;
}

[data-testid="stButton"] > button[kind="primary"]:hover {
  background: var(--accent) !important;
  box-shadow: 0 0 24px var(--accent)88 !important;
}

/* ── Link buttons ────────────────────────────────────────────────────────── */
[data-testid="stLinkButton"] > a {
  background: var(--crimson) !important;
  border: 1px solid var(--accent) !important;
  color: #fff !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.85rem !important;
  letter-spacing: 0.05em;
  box-shadow: 0 0 14px var(--glow) !important;
  border-radius: 3px !important;
  transition: all 0.2s ease !important;
}

[data-testid="stLinkButton"] > a:hover {
  background: var(--accent) !important;
  box-shadow: 0 0 28px var(--accent)88 !important;
}

/* ── Inputs ──────────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] > div > div {
  background: var(--code-bg) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.82rem !important;
  border-radius: 3px !important;
}

[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 8px var(--asp-glow) !important;
  outline: none !important;
}

/* ── Containers / cards ──────────────────────────────────────────────────── */
[data-testid="stContainer"] {
  border-color: var(--border) !important;
}

[data-testid="stContainer"][border="true"],
div[data-testid="stVerticalBlock"] > div[style*="border"] {
  background: var(--bg2) !important;
  border: 1px solid var(--border) !important;
  border-radius: 4px !important;
  box-shadow: 0 0 8px var(--asp-glow) !important;
}

/* ── Metrics ─────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--bg2) !important;
  border: 1px solid var(--border) !important;
  border-radius: 4px !important;
  padding: 12px !important;
}

[data-testid="stMetricValue"] {
  color: var(--accent) !important;
  font-family: 'Cinzel', serif !important;
}

/* ── Progress bars ───────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
  background: var(--bg2) !important;
}

[data-testid="stProgress"] > div > div > div {
  background: linear-gradient(90deg, var(--crimson), var(--accent)) !important;
}

/* ── Dividers ────────────────────────────────────────────────────────────── */
hr {
  border-color: var(--border) !important;
  border-width: 1px 0 0 0 !important;
  box-shadow: 0 0 6px var(--glow) !important;
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-testid="stTab"] {
  font-family: 'JetBrains Mono', monospace !important;
  color: var(--text-dim) !important;
  font-size: 0.8rem !important;
  letter-spacing: 0.04em;
}

[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
  color: var(--accent) !important;
  border-bottom: 2px solid var(--accent) !important;
}

/* ── Alerts / status ─────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
  background: var(--bg2) !important;
  border-left: 3px solid var(--accent) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.82rem !important;
}

/* ── Selectbox ───────────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] label {
  color: var(--text-dim) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.78rem !important;
}

/* ── Toggle ──────────────────────────────────────────────────────────────── */
[data-testid="stToggle"] label {
  color: var(--text) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.82rem !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--violet); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* ── Scanline overlay ────────────────────────────────────────────────────── */
body::after {
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,0.06) 2px,
    rgba(0,0,0,0.06) 4px
  );
  pointer-events: none;
  z-index: 9999;
}

/* ── Sidebar nav links ───────────────────────────────────────────────────── */
[data-testid="stSidebarNavLink"] {
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.8rem !important;
  color: var(--text-dim) !important;
  border-radius: 3px !important;
}

[data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebarNavLink"]:hover {
  background: var(--bg) !important;
  color: var(--accent) !important;
  border-left: 2px solid var(--accent) !important;
}
"""


def inject():
    """Inject Vibesort design system CSS. Call once at the top of each page."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
