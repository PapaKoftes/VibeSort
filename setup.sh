#!/usr/bin/env bash
echo "=== Vibesort Setup ==="
python3 -m pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — fill in your Spotify credentials before running."
fi
mkdir -p outputs staging/playlists data
echo "Done. Run: streamlit run app.py"
