"""
launch.py — Vibesort launcher.  Double-click run.bat (Windows) or bash run.sh (Mac/Linux).

First run:  installs dependencies, creates .env, sets up Streamlit config.
Every run:  kills stale port holders, launches fresh, auto-opens browser.
"""

import os
import re
import sys
import shutil
import subprocess
import threading
import webbrowser
import platform

ROOT         = os.path.dirname(os.path.abspath(__file__))
ENV          = os.path.join(ROOT, ".env")
ENV_EXAMPLE  = os.path.join(ROOT, ".env.example")
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")

PORT_RANGE   = range(8501, 8520)   # scan ports 8501-8519 for stale instances


# ── Python / pip guards ───────────────────────────────────────────────────────

def check_python_version() -> None:
    if sys.version_info < (3, 10):
        print("Vibesort needs Python 3.10 or newer.")
        print("Your version:", sys.version.split()[0])
        print("Download Python: https://www.python.org/downloads/")
        try:
            webbrowser.open("https://www.python.org/downloads/")
        except Exception:
            pass
        sys.exit(1)


def check_pip() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("pip is not available for this Python install.")
        print("Reinstall Python from python.org and enable 'pip' / 'Add to PATH'.")
        sys.exit(1)


# ── Step 0: Dependencies ──────────────────────────────────────────────────────

# Sentinel file: records mtime of requirements.txt when deps were last installed.
# If requirements.txt is newer → reinstall.  Catches any missing/outdated package.
_SENTINEL = os.path.join(ROOT, ".deps_installed")

# Canonical name → importable name (for packages where they differ)
_IMPORT_NAMES = {
    "python-dotenv":  "dotenv",
    "scikit-learn":   "sklearn",
    "pylast":         "pylast",
    "liblistenbrainz":"liblistenbrainz",
    "lyricsgenius":   "lyricsgenius",
    "musicbrainzngs": "musicbrainzngs",
    "langdetect":     "langdetect",
}


def _deps_up_to_date() -> bool:
    """Return True if deps were installed after the last requirements.txt change."""
    if not os.path.exists(_SENTINEL):
        return False
    try:
        req_mtime  = os.path.getmtime(REQUIREMENTS)
        sent_mtime = os.path.getmtime(_SENTINEL)
        if sent_mtime < req_mtime:
            return False
        # Also probe critical imports so a half-broken venv is caught
        import importlib.util
        for pkg in ("streamlit", "spotipy", "dotenv", "requests", "numpy", "pandas"):
            if importlib.util.find_spec(pkg) is None:
                return False
        return True
    except Exception:
        return False


def ensure_dependencies():
    if _deps_up_to_date():
        return

    check_pip()
    print("Installing / updating dependencies (may take 1–2 minutes)...")
    try:
        with open(REQUIREMENTS, encoding="utf-8") as rf:
            for line in rf:
                spec = line.split("#", 1)[0].strip()
                if spec:
                    print(f"  • {spec}")
    except OSError:
        print("  (could not read requirements.txt)")

    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS, "--quiet"]
    )

    # Write sentinel
    try:
        with open(_SENTINEL, "w") as _sf:
            _sf.write(str(os.path.getmtime(REQUIREMENTS)))
    except OSError:
        pass

    print("Dependencies ready.\n")


# ── Step 1: .env ──────────────────────────────────────────────────────────────

def ensure_env():
    if not os.path.exists(ENV):
        src = ENV_EXAMPLE if os.path.exists(ENV_EXAMPLE) else None
        if src:
            shutil.copy(src, ENV)
        else:
            with open(ENV, "w") as f:
                f.write("# Vibesort settings\n")


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


# ── Step 3: Remove legacy SSL files (forced HTTPS on localhost) ──────────────

def cleanup_old_ssl():
    """Delete cert/key files left over from the old HTTPS approach."""
    for fname in ("cert.pem", "key.pem", "ca.crt", "ca.key"):
        path = os.path.join(ROOT, fname)
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"  removed legacy SSL file: {fname}")
        except OSError:
            pass


# ── Step 4: Kill stale port holders ───────────────────────────────────────────

def kill_stale_instances():  # noqa: C901
    """Kill any processes holding Streamlit ports 8501-8519."""
    killed = set()

    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                m = re.search(r":(\d+)\s+\S+\s+LISTENING\s+(\d+)", line)
                if m:
                    port = int(m.group(1))
                    pid  = m.group(2)
                    if port in PORT_RANGE and pid not in killed and pid != "0":
                        subprocess.run(
                            ["taskkill", "/f", "/PID", pid],
                            capture_output=True
                        )
                        killed.add(pid)
                        print(f"  killed PID {pid} (port {port})")
        except Exception as e:
            print(f"  warning: could not kill stale instances: {e}")
    else:
        # macOS / Linux
        for port in PORT_RANGE:
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f"tcp:{port}"],
                    capture_output=True, text=True
                )
                for pid in result.stdout.strip().splitlines():
                    pid = pid.strip()
                    if pid and pid not in killed:
                        subprocess.run(["kill", "-9", pid], capture_output=True)
                        killed.add(pid)
                        print(f"  killed PID {pid} (port {port})")
            except Exception:
                pass

    if killed:
        print(f"  cleared {len(killed)} stale process(es)\n")


# ── Step 4: Launch ────────────────────────────────────────────────────────────

def launch():
    """Start Streamlit, auto-detect port from stdout, open browser."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            os.path.join(ROOT, "app.py"),
            "--browser.gatherUsageStats", "false",
            "--browser.serverAddress",    "localhost",
        ],
        cwd=ROOT, env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )

    browser_opened = threading.Event()

    def pipe_output():
        for line in proc.stdout:
            print(line, end="", flush=True)

            if not browser_opened.is_set():
                # Streamlit prints: "Local URL: http(s)://localhost:XXXX"
                m = re.search(r"Local URL:\s*(https?://\S+)", line)
                if m:
                    url = m.group(1).strip()
                    webbrowser.open(url)
                    browser_opened.set()
                    print(f"\n  Vibesort open at {url}\n")

    reader = threading.Thread(target=pipe_output, daemon=True)
    reader.start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nStopping Vibesort...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Vibesort stopped.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    check_python_version()

    py_ver = sys.version.split()[0]
    print("Vibesort")
    print(f"  Python {py_ver}")
    print(f"  App root: {ROOT}")
    print(f"  Browser: http://localhost:8501 (or next free port 8501–8519)\n")

    ensure_dependencies()
    ensure_env()
    ensure_streamlit_config()

    print("Clearing stale instances...")
    cleanup_old_ssl()
    kill_stale_instances()

    print("Starting Vibesort...\n")
    launch()
