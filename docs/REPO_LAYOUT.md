# Repository layout

## How to run (canonical)

- **Windows:** [`run.bat`](../run.bat) — prefers embedded [`vendor/python/`](../vendor/) when present (portable zip), else system `python`, then runs [`launch.py`](../launch.py).
- **Mac:** [`Vibesort.command`](../Vibesort.command) — double-click in Finder (Python version check + auto-setup dialog). Or [`run.sh`](../run.sh) in Terminal.
- **Linux:** [`run.sh`](../run.sh) — requires `python3`, then runs `launch.py`.
- **Direct:** `python launch.py` from the repo root (Python 3.10+).

[`launch.py`](../launch.py) ensures dependencies, `.env`, Streamlit config, then starts Streamlit on [`app.py`](../app.py).

## Portable Windows zip (maintainer)

[`scripts/`](../scripts/) — [`build_portable.ps1`](../scripts/build_portable.ps1) bundles embeddable Python into `vendor/python/` and produces **`dist/Vibesort-Windows-portable.zip`**. See [`docs/PACKAGING.md`](PACKAGING.md). `vendor/` and `dist/` are gitignored; the zip is not committed.

## Optional / legacy entrypoints

These exist for historical or power-user workflows; the paths above are what README and SETUP describe.

| File | Role |
|------|------|
| [`run.py`](../run.py) | CLI / interactive menu; not the default GUI launcher. |
| [`setup.bat`](../setup.bat) / [`setup.sh`](../setup.sh) | Older setup helpers; prefer `launch.py`. |
| [`gen_cert.py`](../gen_cert.py) | Self-signed TLS for localhost HTTPS experiments; not required for normal HTTP Streamlit. |

## Main code

| Path | Purpose |
|------|---------|
| [`app.py`](../app.py) | Streamlit home / router. |
| [`pages/`](../pages/) | Streamlit multipage UI. |
| [`core/`](../core/) | Ingest, enrich, scoring, deploy, integrations. |
| [`config.py`](../config.py) | Loads `.env` (do not commit `.env`). |
| [`staging/`](../staging/) | Playlist Queue logic (user playlist JSON is gitignored). |
| [`ml/`](../ml/) | Optional feature extraction and local learning scripts. |
| [`tests/`](../tests/) | Pytest. |

## What stays out of git

See [`.gitignore`](../.gitignore): `outputs/` (caches, events, models), `.env`, tokens, personal history JSON, staging playlist data, `vendor/` (embedded Python for portable builds), `dist/` (release zips).
