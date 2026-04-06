#!/usr/bin/env bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

# ── Find Python ───────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Python was not found. Install Python 3.10+ from https://www.python.org/downloads/"
    if command -v xdg-open &>/dev/null; then
        xdg-open "https://www.python.org/downloads/" 2>/dev/null || true
    elif command -v open &>/dev/null; then
        open "https://www.python.org/downloads/" 2>/dev/null || true
    fi
    exit 1
fi

# ── Check version ─────────────────────────────────────────────────────────────
if ! "$PYTHON" -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
    echo "Python 3.10+ required. Found: $("$PYTHON" --version 2>&1)"
    echo "Upgrade from https://www.python.org/downloads/"
    exit 1
fi

# ── First-run auto-setup ──────────────────────────────────────────────────────
if [ ! -f "$HERE/.deps_installed" ]; then
    echo "First run — installing dependencies..."
    bash "$HERE/setup.sh"
fi

# ── Launch ────────────────────────────────────────────────────────────────────
exec "$PYTHON" "$HERE/launch.py"
