# Portable Windows build (zero install for friends)

Friends **do not** install Python. You build a zip **once** on your PC, upload it (Drive, Discord, etc.), they unzip and double-click **`run.bat`**.

`vendor/` is **gitignored** — the portable zip is **not** on GitHub; you create it locally and share the file.

## One command (maintainer)

From the repo root, in **PowerShell** (PowerShell 7: `pwsh`, or Windows PowerShell: `powershell`):

```powershell
pwsh -File scripts\build_portable.ps1
# or: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_portable.ps1
```

This runs:

1. **`build_windows_bundle.ps1`** — downloads [Windows embeddable Python](https://www.python.org/downloads/windows/), enables `import site`, bootstraps pip, installs `requirements.txt` into `vendor/python/`.
2. **`make_portable_zip.ps1`** — writes **`dist\Vibesort-Windows-portable.zip`** (excludes `.git`, `outputs`, `.env`, caches).

Send **`dist\Vibesort-Windows-portable.zip`** only.

## Friend instructions

Included in the zip: **`START_HERE_PORTABLE.txt`**.

Short version: unzip → **`run.bat`** → browser → Connect Spotify.

## Separate steps

```powershell
pwsh -File scripts\build_windows_bundle.ps1
pwsh -File scripts\make_portable_zip.ps1
```

Optional: pick another embeddable version if the download URL 404s:

```powershell
pwsh -File scripts\build_windows_bundle.ps1 -PythonVersion 3.11.9
```

## Size

Roughly **300–600 MB** zipped (Streamlit + scikit-learn + dependencies).

## MSVC runtime

If `scikit-learn` fails to load at runtime, install [Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) (common on fresh Windows).

## PyInstaller `.exe`

Possible later, but Streamlit + one-file EXE is fragile (browser launch, temp dirs). The embeddable-folder approach is the supported path.
