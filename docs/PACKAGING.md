# Windows bundle (no system Python)

Goal: ship a folder where `run.bat` uses a **bundled** Python under `vendor/python/` so end users do not install Python.

## Layout after build

```
Vibesort/
  run.bat          # prefers vendor\python\python.exe when present
  launch.py
  vendor/
    python/        # Windows embeddable CPython + site-packages
```

Approximate size: **300–600 MB** (Streamlit, scikit-learn, dependencies).

## Maintainer steps (outline)

1. Download **Windows embeddable** Python 3.10+ from [python.org](https://www.python.org/downloads/windows/).
2. Extract into `vendor/python/`.
3. Uncomment `import site` in `vendor/python/python310._pth` (filename matches version).
4. Run `vendor\python\python.exe -m pip install --upgrade pip` (bootstrap pip per embeddable docs).
5. `vendor\python\python.exe -m pip install -r requirements.txt`.
6. Zip the repo **without** `outputs/`, `.env`, or user caches.

`run.bat` automatically invokes `vendor\python\python.exe` when that file exists.

## Script

See [`scripts/build_windows_bundle.ps1`](../scripts/build_windows_bundle.ps1) for an automated download/bootstrap (requires PowerShell and network). Review paths and Python version before running.

## PyInstaller `.exe`

Possible later, but Streamlit + one-file EXE is fragile (browser launch, temp dirs). Prefer the embeddable folder approach first.
