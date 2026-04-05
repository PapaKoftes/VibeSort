#!/usr/bin/env bash
set -e
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.10+ from https://www.python.org/downloads/"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "https://www.python.org/downloads/" 2>/dev/null || true
  elif command -v open >/dev/null 2>&1; then
    open "https://www.python.org/downloads/" 2>/dev/null || true
  fi
  exit 1
fi
exec python3 launch.py
