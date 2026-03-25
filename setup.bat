@echo off
echo === Vibesort Setup ===
pip install -r requirements.txt
if not exist .env copy .env.example .env && echo Created .env — fill in your Spotify credentials before running.
if not exist outputs mkdir outputs
if not exist staging\playlists mkdir staging\playlists
if not exist data mkdir data
echo.
echo Done.
echo.
echo Standard run (add http://localhost:8501 as redirect URI in Spotify dashboard):
echo   streamlit run app.py
echo.
echo HTTPS run (if Spotify blocks http — run gen_cert.py first, then):
echo   streamlit run app.py --server.sslCertFile cert.pem --server.sslKeyFile key.pem
echo   (Use https://localhost:8501 as redirect URI and in .env)
echo.
pause
