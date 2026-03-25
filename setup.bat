@echo off
echo === Vibesort Setup ===
pip install -r requirements.txt
if not exist .env copy .env.example .env && echo Created .env — fill in your Spotify credentials before running.
if not exist outputs mkdir outputs
if not exist staging\playlists mkdir staging\playlists
if not exist data mkdir data
echo.
echo Done. To run Vibesort:
echo   python launch.py
echo.
pause
