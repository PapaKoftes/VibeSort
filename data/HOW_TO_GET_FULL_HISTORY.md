# How to get your full Spotify listening history

Spotify's API only shows your top 50 tracks. Your complete history requires a data export.

## Steps

1. Go to [spotify.com/account/privacy](https://www.spotify.com/account/privacy/)
2. Scroll to **"Download your data"**
3. Select **"Extended streaming history"**
4. Click **Request data** — Spotify emails you a link in up to 30 days
5. Unzip and copy all `StreamingHistory_music_*.json` files into this `data/` folder
6. Launch Vibesort (`run.bat`, `run.sh`, or `python launch.py`) and run **Scan Library** — export files in `data/` are picked up automatically (same pattern as [`core/history_parser.py`](../core/history_parser.py))

## What you unlock

- Accurate play counts per track
- Total hours listened
- "All Time Favourites" playlist from your actual most-played songs
- More accurate taste stats

## Alternative: stats.fm

[stats.fm](https://stats.fm) accepts the same data export and gives you a permanent dashboard with play counts, listening trends, and year-over-year stats. Free tier is generous.
