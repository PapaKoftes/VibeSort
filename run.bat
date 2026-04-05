@echo off
setlocal
set "HERE=%~dp0"
set "VENDOR_PY=%HERE%vendor\python\python.exe"
if exist "%VENDOR_PY%" (
  "%VENDOR_PY%" "%HERE%launch.py"
  pause
  goto :eof
)
where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3.10+ from https://www.python.org/downloads/
  echo Or build a vendor bundle: see docs\PACKAGING.md and scripts\build_windows_bundle.ps1
  echo Enable "Add python.exe to PATH" during setup on Windows.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
python "%HERE%launch.py"
pause
