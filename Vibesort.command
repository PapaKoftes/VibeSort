#!/usr/bin/env bash
# Vibesort — Mac launcher
# Double-click this file in Finder to open Vibesort.
# If macOS says "cannot be opened because it is from an unidentified developer":
#   Right-click → Open → Open anyway
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

# ── Find Python ───────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null)
        if [ "$VER" = "True" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display dialog "Python 3.10+ is required.\n\nClick OK to open the Python download page, then install Python and run Vibesort.command again." buttons {"OK"} default button "OK" with title "Vibesort"'
    open "https://www.python.org/downloads/"
    exit 1
fi

# ── First-run auto-setup ──────────────────────────────────────────────────────
if [ ! -f "$HERE/.deps_installed" ]; then
    osascript -e 'display dialog "First launch — installing dependencies.\n\nThis takes 1-2 minutes. The app will open automatically when ready." buttons {"OK"} default button "OK" with title "Vibesort"'
    bash "$HERE/setup.sh"
fi

# ── Launch ────────────────────────────────────────────────────────────────────
exec "$PYTHON" "$HERE/launch.py"
