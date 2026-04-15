# Vibesort Terms of Use

_Last updated: 2026-04-15_

## 1. What Vibesort Is

Vibesort is a free, open-source tool that reads your Spotify library and organises it into mood, genre, era, and artist playlists. It runs locally on your machine. There is no Vibesort server, no account, and no cloud storage.

## 2. Your Data

- All processing happens on your machine. Your library data stays on your machine.
- Vibesort queries third-party APIs (Spotify, Last.fm, Deezer, MusicBrainz, lrclib.net) to enrich your library with tags, genres, and lyrics. Only track/artist names are sent to these services.
- Your Spotify credentials are stored locally in `.env` and never transmitted to any Vibesort server.
- See [PRIVACY.md](PRIVACY.md) for full details on what data is accessed and how.

## 3. Spotify API Usage

Vibesort uses the Spotify Web API under Spotify's [Developer Policy](https://developer.spotify.com/policy) and [Terms of Service](https://developer.spotify.com/terms). By using Vibesort:

- You agree to Spotify's [Terms of Service](https://www.spotify.com/legal/end-user-agreement/)
- You are responsible for your own Spotify account and credentials
- Vibesort only creates playlists you explicitly deploy — it does not modify, rename, or delete existing playlists
- Vibesort does not download, reproduce, or redistribute Spotify audio content

## 4. Open Source License

Vibesort is released under the **MIT License**. You are free to:

- Use it for personal or commercial purposes
- Modify and distribute it
- Use it privately

You must include the original copyright notice and license in any distribution.

```
MIT License

Copyright (c) 2026 Vibesort Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 5. Third-Party Services

Vibesort integrates with these services. Their own terms apply when you use them:

| Service | Terms | Notes |
|---|---|---|
| Spotify | [Terms](https://www.spotify.com/legal/end-user-agreement/) | Required |
| Last.fm | [Terms](https://www.last.fm/legal/terms) | Optional |
| Deezer | [Terms](https://www.deezer.com/legal/cgu) | Built-in, no login |
| MusicBrainz | [Terms](https://metabrainz.org/doc/Terms_of_Use) | Built-in, no login |
| lrclib.net | [Terms](https://lrclib.net/docs) | Built-in, no login |
| Genius | [Terms](https://genius.com/static/terms) | Optional |
| ListenBrainz | [Terms](https://metabrainz.org/doc/Terms_of_Use) | Optional |

## 6. No Warranty

Vibesort is provided as-is, without warranty of any kind. Playlist results depend on data quality from Spotify and third-party enrichment sources. Coverage and accuracy will vary by library.

## 7. Spotify Extended Quota Application

This document, together with [PRIVACY.md](PRIVACY.md), serves as the privacy policy and terms of service required for Spotify's Extended Quota Mode application. Key points for Spotify's review:

- **Data handling:** User library data is processed locally. Only artist/track names are sent to Spotify's own API.
- **Playlist writes:** Vibesort only writes playlists that users explicitly deploy via the Staging interface. No other writes occur.
- **No data sharing:** No user data is shared with third parties beyond the APIs listed above.
- **No commercialisation of Spotify data:** Vibesort does not sell, rent, or monetise any data obtained from Spotify's APIs.
- **Compliance:** Vibesort complies with Spotify's Developer Policy, including restrictions on audio analysis, data storage, and commercial use.

## 8. Contact

For questions, issues, or to report a bug: [github.com/PapaKoftes/VibeSort/issues](https://github.com/PapaKoftes/VibeSort/issues)
