"""
launch.py — Vibesort launcher.  Double-click run.bat (Windows) or bash run.sh (Mac/Linux).

First run:  installs dependencies, creates .env, sets up Streamlit config.
Every run:  launches the app at http://localhost:8501
"""

import os
import sys
import subprocess
import shutil

ROOT         = os.path.dirname(os.path.abspath(__file__))
ENV          = os.path.join(ROOT, ".env")
ENV_EXAMPLE  = os.path.join(ROOT, ".env.example")
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")
APP_URL      = "http://localhost:8501"


# ── Step 0: Dependencies ──────────────────────────────────────────────────────

def ensure_dependencies():
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("Installing dependencies (first run — takes ~1 min)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS]
        )
        print("Done.\n")


# ── Step 1: .env ──────────────────────────────────────────────────────────────

def ensure_env():
    if not os.path.exists(ENV):
        src = ENV_EXAMPLE if os.path.exists(ENV_EXAMPLE) else None
        if src:
            shutil.copy(src, ENV)
        else:
            with open(ENV, "w") as f:
                f.write("# Vibesort settings\n")
        # Don't stop — shared client ID is baked into config.py, app works immediately


# ── Step 2: Streamlit config (suppress email prompt, dark theme) ──────────────

def ensure_streamlit_config():
    config_content = (
        "[browser]\ngatherUsageStats = false\n\n"
        "[server]\nheadless = false\n\n"
        '[theme]\nbase = "dark"\n'
    )
    credentials_content = '[general]\nemail = ""\n'

    for config_dir in (
        os.path.join(os.path.expanduser("~"), ".streamlit"),
        os.path.join(ROOT, ".streamlit"),
    ):
        os.makedirs(config_dir, exist_ok=True)
        for fname, content in (
            ("config.toml",      config_content),
            ("credentials.toml", credentials_content),
        ):
            path = os.path.join(config_dir, fname)
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)


# ── Step 3: Launch ────────────────────────────────────────────────────────────

def launch():
    print(f"Starting Vibesort @ {APP_URL}\n")
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    try:
        subprocess.run(
            [
                sys.executable, "-m", "streamlit", "run",
                os.path.join(ROOT, "app.py"),
                "--browser.gatherUsageStats", "false",
            ],
            cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
        )
    except KeyboardInterrupt:
        print("\nVibesort stopped.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_dependencies()
    ensure_env()
    ensure_streamlit_config()
    launch()
