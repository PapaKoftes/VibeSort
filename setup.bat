@echo off
setlocal
echo === Vibesort Setup ===
echo.

REM ── Check Python is available ─────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on this machine.
    echo.
    echo Please install Python 3.10 or newer from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: On the installer, tick "Add python.exe to PATH" before clicking Install.
    echo After installing, close this window and run setup.bat again.
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

REM ── Check Python version >= 3.10 ─────────────────────────────────────────
python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.10 or newer is required.
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   Found: %%v
    echo.
    echo Please upgrade Python from https://www.python.org/downloads/
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo Python: %%v

REM ── Install dependencies ──────────────────────────────────────────────────
echo Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    echo Check the error above, then re-run setup.bat.
    pause
    exit /b 1
)

REM ── Create .env if missing ────────────────────────────────────────────────
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo Created .env from .env.example
    ) else (
        echo # Vibesort settings > .env
        echo Created blank .env
    )
)

REM ── Create required directories ───────────────────────────────────────────
if not exist outputs       mkdir outputs
if not exist staging       mkdir staging
if not exist staging\playlists mkdir staging\playlists
if not exist data          mkdir data

REM ── Mark deps as installed ────────────────────────────────────────────────
python -c "import os; open('.deps_installed','w').write(str(os.path.getmtime('requirements.txt')))" >nul 2>&1

echo.
echo Setup complete. To start Vibesort, double-click run.bat
echo.
pause
