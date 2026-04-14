# Vibesort — setup for non-developers

You do **not** need Git or a Spotify developer account for the default setup.

## Portable zip (Windows, no Python)

If someone sent you **`Vibesort-Windows-portable.zip`**: unzip the folder anywhere, then double-click **`run.bat`**. The first launch may take a minute while dependencies finish unpacking. Skip **Install Python** below.

## 1. Install Python

1. Open [python.org/downloads](https://www.python.org/downloads/).
2. Download **Python 3.10 or newer** for your system (Windows, macOS, or Linux).
3. Run the installer.
4. **Windows:** enable **“Add python.exe to PATH”**, then finish the install.

If you skip PATH on Windows, double-clicking `run.bat` may say `'python' is not recognized` — reinstall Python with PATH enabled.

## 2. Get Vibesort

- **ZIP:** On [GitHub](https://github.com/PapaKoftes/VibeSort), use **Code → Download ZIP**, then unpack the folder anywhere you like.
- **Git (optional):** `git clone` the repo if you already use Git.

## 3. Run the app

**Windows:** double-click **`run.bat`**.

**Mac or Linux:** in Terminal, `cd` into the Vibesort folder, then:

```bash
bash run.sh
```

> **Mac shortcut:** You can also double-click **`Vibesort.command`** in Finder instead of using Terminal. If macOS blocks it, right-click → Open → Open anyway (one-time only).

The first launch installs dependencies (one or two minutes), creates a `.env` file if needed, then opens your browser. Click **Connect to Spotify** and sign in.

## 4. Optional: extra data sources

Edit the `.env` file in the Vibesort folder (created on first run) to add free API keys — see **Settings** inside the app for copy-paste examples. Nothing is required for basic genre + Discogs + lyrics enrichment.

## Troubleshooting

| Problem | What to do |
|--------|------------|
| `python` / `python3` not found | Install Python from python.org and enable PATH (Windows). |
| Browser does not open | Go to `http://localhost:8501` manually. |
| Spotify login fails | The shared app may be in Development Mode; see the README note or use your own app ID in `.env`. |

Maintainers: to ship a **portable zip** for friends (no Python install), run `pwsh -File scripts\build_portable.ps1` (or `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_portable.ps1`) and share `dist\Vibesort-Windows-portable.zip` — see [docs/PACKAGING.md](docs/PACKAGING.md).

For more detail, see [README.md](README.md).
