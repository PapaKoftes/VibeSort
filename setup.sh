#!/usr/bin/env bash
echo "=== Vibesort Setup ==="
python3 -m pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — fill in your Spotify credentials before running."
fi
mkdir -p outputs staging/playlists data
echo ""
echo "Done. To run Vibesort:"
echo "  python3 launch.py"
echo ""
