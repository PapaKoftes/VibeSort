@echo off
setlocal
set "HERE=%~dp0"
set "VENDOR_PY=%HERE%vendor\python\python.exe"

REM ── Use vendored Python if available (portable bundle) ────────────────────
if exist "%VENDOR_PY%" (
    "%VENDOR_PY%" "%HERE%launch.py"
    pause
    goto :eof
)

REM ── Check Python is on PATH ───────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo Python was not found.
    echo.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Tick "Add python.exe to PATH" during installation, then run this again.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

REM ── First-run auto-setup: if deps sentinel missing, run setup silently ────
if not exist "%HERE%.deps_installed" (
    echo First run detected — installing dependencies...
    echo.
    call "%HERE%setup.bat"
    if errorlevel 1 (
        echo Setup failed. Fix the error above and try again.
        pause
        exit /b 1
    )
)

REM ── Launch ────────────────────────────────────────────────────────────────
python "%HERE%launch.py"
pause
