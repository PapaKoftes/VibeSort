# Repository layout

## How to run (canonical)

- **Windows:** [`run.bat`](../run.bat) — checks for `python`, then runs [`launch.py`](../launch.py).
- **Mac / Linux:** [`run.sh`](../run.sh) — requires `python3`, then runs `launch.py`.
- **Direct:** `python launch.py` from the repo root (Python 3.10+).

[`launch.py`](../launch.py) ensures dependencies, `.env`, Streamlit config, then starts Streamlit on [`app.py`](../app.py).

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
| [`staging/`](../staging/) | Staging shelf logic (user playlist JSON is gitignored). |
| [`ml/`](../ml/) | Optional feature extraction and local learning scripts. |
| [`tests/`](../tests/) | Pytest. |

## What stays out of git

See [`.gitignore`](../.gitignore): `outputs/` (caches, events, models), `.env`, tokens, personal history JSON, staging playlist data.
