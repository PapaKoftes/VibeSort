#!/usr/bin/env bash
set -e
echo "=== Vibesort Setup ==="
echo ""

# ── Check Python ──────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python was not found."
    echo ""
    echo "Install Python 3.10+ from https://www.python.org/downloads/"
    echo "  macOS:  brew install python  (or download from python.org)"
    echo "  Linux:  sudo apt install python3 python3-pip"
    if command -v open &>/dev/null; then
        open "https://www.python.org/downloads/"
    fi
    exit 1
fi

# ── Check Python version ──────────────────────────────────────────────────────
if ! "$PYTHON" -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
    VER=$("$PYTHON" --version 2>&1)
    echo "ERROR: Python 3.10+ required. Found: $VER"
    echo "Upgrade from https://www.python.org/downloads/"
    if command -v open &>/dev/null; then
        open "https://www.python.org/downloads/"
    fi
    exit 1
fi

echo "Python: $("$PYTHON" --version)"

# ── Install dependencies ──────────────────────────────────────────────────────
echo "Installing dependencies..."
"$PYTHON" -m pip install --upgrade pip --quiet
"$PYTHON" -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Dependency installation failed. Check the error above."
    exit 1
fi

# ── Create .env if missing ────────────────────────────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Created .env from .env.example"
    else
        echo "# Vibesort settings" > .env
        echo "Created blank .env"
    fi
fi

# ── Create required directories ───────────────────────────────────────────────
mkdir -p outputs staging/playlists data

# ── Mark deps as installed ────────────────────────────────────────────────────
"$PYTHON" -c "import os; open('.deps_installed','w').write(str(os.path.getmtime('requirements.txt')))" 2>/dev/null || true

echo ""
echo "Setup complete. To start Vibesort:"
echo "  bash run.sh  (or double-click run.bat on Windows)"
echo ""
