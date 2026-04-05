"""
core/theme.py — Vibesort design system.

Call inject() at the top of every Streamlit page.

Strategy: apply colors, fonts, glows only.
Never touch layout, spacing, sizing, or Streamlit's structural chrome.
"""

import streamlit as st

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Cinzel:wght@400;600;700;900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0');

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
}

/* ── Backgrounds ─────────────────────────────────────────────────────────── */
.stApp, [data-testid="stAppViewContainer"] {
  background-color: var(--bg) !important;
}
[data-testid="stSidebar"] > div:first-child {
  background-color: var(--bg2) !important;
}
[data-testid="stHeader"] {
  background-color: var(--bg) !important;
  border-bottom: 1px solid var(--border) !important;
}
[data-testid="stToolbar"] {
  background-color: var(--bg) !important;
}
[data-testid="stDecoration"] {
  background-image: none !important;
  background-color: var(--crimson) !important;
  height: 2px !important;
}

/* ── Global text + font ──────────────────────────────────────────────────── */
/* Do not force monospace on bare `span` — it breaks Streamlit Material icon ligatures
   (shows "keyboard_double_arrow_right" text on sidebar / expanders). */
html, body, p, div, li, td, th, label,
.stMarkdown, [data-testid="stText"],
[data-testid="stMarkdownContainer"] {
  font-family: 'JetBrains Mono', 'Courier New', monospace !important;
  color: var(--text) !important;
}
[data-testid="stMarkdownContainer"] span,
.stMarkdown span {
  font-family: 'JetBrains Mono', 'Courier New', monospace !important;
}
/* Streamlit chrome: keep default UI font + Material Symbols for icons */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] *,
[data-testid="stSidebarNav"] a,
[data-testid="stSidebarNav"] span,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary *,
button[kind="header"],
button[kind="headerNoPadding"],
button[kind="headerNoPadding"] * {
  font-family: "Source Sans Pro", sans-serif !important;
}
span.material-symbols-outlined,
.material-symbols-outlined {
  font-family: 'Material Symbols Outlined', sans-serif !important;
  font-weight: normal !important;
  font-style: normal !important;
  font-size: 1.25rem !important;
  letter-spacing: normal !important;
  text-transform: none !important;
  white-space: nowrap !important;
}

/* ── Headings — Cinzel + accent glow ─────────────────────────────────────── */
h1, h2, h3, h4,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
  font-family: 'Cinzel', Georgia, serif !important;
  color: var(--accent) !important;
  letter-spacing: 0.05em !important;
}
/* Breathing only on page-level h1 */
h1, .stMarkdown h1 {
  text-shadow: 0 0 12px var(--glow);
  animation: title-breathe 4s ease-in-out infinite;
}
@keyframes title-breathe {
  0%, 100% { text-shadow: 0 0 6px var(--glow); }
  50%       { text-shadow: 0 0 28px #c0006a44; }
}
h2, h3, .stMarkdown h2, .stMarkdown h3 {
  color: var(--text) !important;
  font-family: 'Cinzel', serif !important;
}

/* ── Caption / dim text ──────────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
  color: var(--text-dim) !important;
  font-family: 'JetBrains Mono', monospace !important;
}

/* ── Metric values ───────────────────────────────────────────────────────── */
[data-testid="stMetricValue"] {
  color: var(--accent) !important;
  font-family: 'Cinzel', serif !important;
}
[data-testid="stMetricLabel"] {
  color: var(--text-dim) !important;
  font-family: 'JetBrains Mono', monospace !important;
}
[data-testid="stMetricDelta"] {
  font-family: 'JetBrains Mono', monospace !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
[data-testid="stBaseButton-secondary"] > button,
[data-testid="stBaseButton-secondary"] {
  background: transparent !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  font-family: 'JetBrains Mono', monospace !important;
  letter-spacing: 0.03em !important;
  transition: border-color 0.15s, color 0.15s, box-shadow 0.15s !important;
}
[data-testid="stBaseButton-secondary"]:hover > button,
[data-testid="stBaseButton-secondary"] > button:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
  box-shadow: 0 0 8px var(--glow) !important;
}
[data-testid="stBaseButton-primary"] > button,
[data-testid="stBaseButton-primary"] {
  background: var(--crimson) !important;
  border: 1px solid var(--accent) !important;
  color: #fff !important;
  font-family: 'JetBrains Mono', monospace !important;
  letter-spacing: 0.03em !important;
  box-shadow: 0 0 10px var(--glow) !important;
  transition: all 0.15s !important;
}
[data-testid="stBaseButton-primary"]:hover > button,
[data-testid="stBaseButton-primary"] > button:hover {
  background: var(--accent) !important;
  box-shadow: 0 0 20px #c0006a55 !important;
}

/* ── Link button ─────────────────────────────────────────────────────────── */
[data-testid="stLinkButton"] a {
  background: var(--crimson) !important;
  border: 1px solid var(--accent) !important;
  color: #fff !important;
  font-family: 'JetBrains Mono', monospace !important;
  box-shadow: 0 0 10px var(--glow) !important;
  transition: all 0.15s !important;
}
[data-testid="stLinkButton"] a:hover {
  background: var(--accent) !important;
  box-shadow: 0 0 22px #c0006a66 !important;
}

/* ── Inputs ──────────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
  background: var(--code-bg) !important;
  border-color: var(--border) !important;
  color: var(--text) !important;
  font-family: 'JetBrains Mono', monospace !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 6px var(--glow) !important;
}

/* ── Selectbox / dropdown ────────────────────────────────────────────────── */
[data-testid="stSelectbox"] label,
[data-testid="stSelectbox"] span {
  color: var(--text-dim) !important;
  font-family: 'JetBrains Mono', monospace !important;
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] button {
  font-family: 'JetBrains Mono', monospace !important;
  color: var(--text-dim) !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
  color: var(--accent) !important;
  border-bottom-color: var(--accent) !important;
}

/* ── Divider ─────────────────────────────────────────────────────────────── */
hr {
  border-color: var(--border) !important;
}

/* ── Code blocks ─────────────────────────────────────────────────────────── */
code, pre, [data-testid="stCode"] {
  background: var(--code-bg) !important;
  color: var(--accent) !important;
  font-family: 'JetBrains Mono', monospace !important;
  border: 1px solid var(--border) !important;
}

/* ── Progress bar ────────────────────────────────────────────────────────── */
[role="progressbar"] > div {
  background: linear-gradient(90deg, var(--crimson), var(--accent)) !important;
}

/* ── Alerts ──────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
  background: var(--bg2) !important;
  border-left-color: var(--accent) !important;
}
[data-testid="stAlert"] p {
  font-family: 'JetBrains Mono', monospace !important;
}

/* ── Success/info/warning/error banners ──────────────────────────────────── */
[data-testid="stAlertSuccess"]  { border-left-color: #2d6a2d !important; }
[data-testid="stAlertInfo"]     { border-left-color: var(--violet) !important; }
[data-testid="stAlertWarning"]  { border-left-color: #8b6000 !important; }
[data-testid="stAlertError"]    { border-left-color: var(--crimson) !important; }

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar       { width: 5px; height: 5px; }
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
    transparent 0px,
    transparent 2px,
    rgba(0,0,0,0.04) 2px,
    rgba(0,0,0,0.04) 4px
  );
  pointer-events: none;
  z-index: 9998;
}

/* ── Music glyph background layer ───────────────────────────────────────── */
/* Injected via JS below; CSS controls the glyph appearance */
.vs-glyph {
  position: fixed;
  font-size: 1.4rem;
  color: rgba(255,255,255,0.07);
  pointer-events: none;
  z-index: 0;
  user-select: none;
  animation: glyph-breathe var(--dur, 5s) ease-in-out infinite;
  animation-delay: var(--delay, 0s);
  will-change: opacity;
}
@keyframes glyph-breathe {
  0%,100% { opacity: 0.03; transform: scale(1);   }
  50%      { opacity: 0.13; transform: scale(1.08); }
}

/* ── Sidebar nav ─────────────────────────────────────────────────────────── */
[data-testid="stSidebarNav"] a {
  font-family: 'JetBrains Mono', monospace !important;
  color: var(--text-dim) !important;
}
[data-testid="stSidebarNav"] a:hover,
[data-testid="stSidebarNav"] a[aria-current="page"] {
  color: var(--accent) !important;
  border-left: 2px solid var(--accent) !important;
  background: transparent !important;
}

/* ── Toggle ──────────────────────────────────────────────────────────────── */
[data-testid="stToggle"] p {
  font-family: 'JetBrains Mono', monospace !important;
  color: var(--text) !important;
}

/* ── Dataframe / table ───────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
}
"""


_GLYPHS_JS = """
<script>
(function() {
  if (document.getElementById('vs-glyphs')) return;
  var GLYPHS = [
    '♩','♪','♫','♬','𝄞','𝄢','𝄡','𝄠','𝄟','𝄻','𝄼','𝄽','𝄾','𝄿',
    '𝅗𝅥','𝅘𝅥𝅮','𝅘𝅥𝅯','𝅘𝅥𝅰','𝅘𝅥𝅱','𝅘𝅥𝅲',
    '🎵','🎶','🎼','🎹','🎸','🥁','🎷','🎺','🎻','🪗','🪘','🎤',
  ];
  var layer = document.createElement('div');
  layer.id = 'vs-glyphs';
  layer.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:0;overflow:hidden';
  var count = 28;
  for (var i = 0; i < count; i++) {
    var el = document.createElement('span');
    el.className = 'vs-glyph';
    el.textContent = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
    var x = Math.random() * 98;
    var y = Math.random() * 95;
    var dur = (4 + Math.random() * 6).toFixed(1);
    var delay = (Math.random() * -8).toFixed(1);
    var size = (1.0 + Math.random() * 1.4).toFixed(2);
    el.style.cssText =
      'left:' + x + '%;top:' + y + '%;' +
      'font-size:' + size + 'rem;' +
      '--dur:' + dur + 's;--delay:' + delay + 's;';
    layer.appendChild(el);
  }
  // Insert after body renders — retry until stApp exists
  var tries = 0;
  function tryInsert() {
    var app = document.querySelector('[data-testid="stAppViewContainer"]') || document.body;
    if (app) { app.insertBefore(layer, app.firstChild); }
    else if (++tries < 20) { setTimeout(tryInsert, 300); }
  }
  tryInsert();
})();
</script>
"""


def inject():
    """Inject Vibesort design system. Call once at the top of each page."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
    st.markdown(_GLYPHS_JS, unsafe_allow_html=True)


def render_scan_quality_strip(vibesort: dict, title: str = "Scan Data Quality") -> None:
    """
    Compact signal/provenance strip for pages that depend on scan quality.
    """
    flags = (vibesort or {}).get("scan_flags", {})
    meta = (vibesort or {}).get("scan_meta", {})
    weights = flags.get("weights", (0.0, 0.0, 0.0, 0.0))
    corpus_mode = meta.get("corpus_mode", "full_library")
    corpus_label = "Liked songs only" if corpus_mode == "liked_only" else "Full library"

    def _badge(ok: bool, label: str) -> str:
        return f"{'✅' if ok else '⚠️'} {label}"

    import config as _cfg

    _lb_token = bool(getattr(_cfg, "LISTENBRAINZ_TOKEN", "").strip())
    _lb_user = bool(getattr(_cfg, "LISTENBRAINZ_USERNAME", "").strip())
    _lb_configured = _lb_token and _lb_user
    _lb_matched = bool(flags.get("has_listenbrainz", False))
    if _lb_matched:
        _lb_line = "✅ listenbrainz (listening history matched library tracks)"
    elif _lb_configured:
        _lb_line = "ℹ️ listenbrainz (token set — no listens overlapped this library; boosts inactive)"
    else:
        _lb_line = "⚠️ listenbrainz (add LISTENBRAINZ_TOKEN + USERNAME in .env)"

    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.caption(
            " · ".join(
                [
                    _badge(flags.get("has_tags", False), "tags"),
                    _badge(flags.get("has_genres", False), "genres"),
                    _badge(flags.get("has_lyrics", False), "lyrics"),
                    _lb_line,
                    _badge(flags.get("has_audio", False), "audio"),
                ]
            )
        )
        st.caption(
            f"Corpus: {corpus_label} | "
            f"Weights A/T/S/G: {weights[0]:.2f}/{weights[1]:.2f}/{weights[2]:.2f}/{weights[3]:.2f}"
        )
