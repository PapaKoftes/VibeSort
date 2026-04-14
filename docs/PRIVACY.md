# Vibesort Privacy Policy

_Last updated: 2026-04-14_

## What Vibesort Is

Vibesort is an open-source, locally-run application. It runs entirely on your own machine. There is no Vibesort server, no cloud account, and no data collection by the project maintainers.

---

## Data We Access

### Spotify
Vibesort requests the following Spotify permissions (OAuth scopes):

| Scope | Purpose |
|---|---|
| `user-library-read` | Read your Liked Songs |
| `user-top-read` | Read your top tracks and artists |
| `user-follow-read` | Read your followed artists |
| `playlist-read-private` | Read your private playlists (for mining mood tags) |
| `playlist-read-collaborative` | Read collaborative playlists |
| `playlist-modify-private` | Create/update playlists you deploy |
| `playlist-modify-public` | Create/update public playlists you deploy |

Vibesort **only creates playlists you explicitly deploy** via the Staging page. It never modifies, renames, or deletes existing playlists.

### Optional Services
If you configure them, Vibesort also accesses:
- **Last.fm** — public artist and track tags via the Last.fm API (no password stored)
- **ListenBrainz** — your listening history via your personal API token
- **Deezer** — public genre and BPM data (no account required)
- **Genius** — lyrics via your personal API key
- **lrclib.net / lyrics.ovh** — lyrics (no account required, public API)
- **Discogs** — public release data (no account required)
- **MusicBrainz** — public metadata (no account required)

---

## Data Storage

All data is stored **locally on your machine** in the `data/` and `outputs/` directories inside the Vibesort folder:

| Location | Contents |
|---|---|
| `data/cache/` | Enrichment results (Last.fm tags, Deezer data, lyrics) |
| `outputs/.last_scan_snapshot.json` | Your last scan result |
| `.env` | API keys and credentials (never committed to git) |
| `.vibesort_pkce_token.json` | Spotify OAuth token (local only) |

**None of this data leaves your machine** except for the API calls required to fetch it (e.g. a query to Last.fm's API to get tags for an artist).

---

## What We Don't Do

- We do not collect analytics or telemetry
- We do not send your library data to any Vibesort server (there isn't one)
- We do not store your Spotify credentials — only the OAuth access token, locally
- We do not share your data with third parties beyond the APIs listed above
- We do not use your data for advertising or profiling

---

## Third-Party APIs

When Vibesort queries external APIs (Last.fm, Deezer, MusicBrainz, etc.), those services receive the **track/artist name** being looked up. Their own privacy policies apply:

- [Last.fm Privacy Policy](https://www.last.fm/legal/privacy)
- [Spotify Privacy Policy](https://www.spotify.com/legal/privacy-policy/)
- [MusicBrainz Privacy Policy](https://metabrainz.org/privacy)
- [Deezer Privacy Policy](https://www.deezer.com/legal/personal-datas)

---

## Spotify Extended Quota

If you apply for Spotify Extended Quota (to allow more than 25 users in Development Mode), Spotify requires a privacy policy as part of the review. This document fulfils that requirement.

Vibesort's data handling is minimal: we read library metadata to score and sort it, and we write playlists back to your account only when you explicitly deploy them.

---

## Contact

Questions? Open an issue at [github.com/PapaKoftes/VibeSort/issues](https://github.com/PapaKoftes/VibeSort/issues).
