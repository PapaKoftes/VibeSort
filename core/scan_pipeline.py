"""
scan_pipeline.py — Shared library scan used by Streamlit and run.py.

Keeps ingest → enrich → mining → optional sources → profiles → mood playlists
in one place so CLI and UI stay aligned.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from core import history_parser
from core import ingest, enrich
from core import genre as genre_mod
from core import playlist_mining
from core import profile as profile_mod
from core import scorer, cohesion as cohesion_mod
from core.mood_graph import all_moods


def execute_library_scan(
    sp,
    user_id: str,
    cfg,
    step: Callable[[str, int], None],
    *,
    force_refresh: bool = False,
    refresh_spotify_token: Callable[[], object | None] | None = None,
    min_score_override: float | None = None,
    strictness: int = 3,
    playlist_min_size: int = 20,
    playlist_expansion: bool = True,
    allow_mvp_fallback: bool | None = None,
    mvp_min_playlist_size: int | None = None,
    mvp_score_floor: float | None = None,
    corpus_mode: str = "full_library",
    lyric_weight: float = 1.16,
    max_tracks_cap: int | None = None,
) -> tuple[dict | None, dict | None]:
    """
    Run full scan. Returns (vibesort_payload, lyrics_lang_map_or_none).

    step(msg, pct): progress callback; pct in 0–100.
    refresh_spotify_token: optional callable (e.g. PKCE refresh) before heavy API use.
    """
    _allow_mvp = cfg.ALLOW_MVP_FALLBACK if allow_mvp_fallback is None else allow_mvp_fallback
    _mvp_n = cfg.MVP_MIN_PLAYLIST_SIZE if mvp_min_playlist_size is None else mvp_min_playlist_size
    _mvp_floor = cfg.MVP_SCORE_FLOOR if mvp_score_floor is None else mvp_score_floor

    cfg.SCAN_LYRIC_WEIGHT = float(lyric_weight)

    _max_tracks_cap = max_tracks_cap if max_tracks_cap is not None else cfg.MAX_TRACKS_PER_PLAYLIST

    _cohesion_thresh = cfg.COHESION_THRESHOLD + (strictness - 3) * 0.05
    _drop_ratio = max(0.05, 0.10 + (strictness - 3) * 0.05)
    _ensure_target = playlist_min_size if playlist_expansion else 0
    _strict_backfill = playlist_expansion

    if refresh_spotify_token:
        try:
            new_sp = refresh_spotify_token()
            if new_sp is not None:
                sp = new_sp
        except Exception:
            pass

    # Step 1: Ingest
    if corpus_mode == "liked_only":
        step("Collecting liked songs only...", 5)
        all_tracks = ingest.liked_songs(sp)
        top_tracks_list = []
        top_artists_list = []
    else:
        step("Collecting liked songs, top tracks, and followed artists...", 5)
        all_tracks, top_tracks_list, top_artists_list = ingest.collect(sp, cfg)
    step(f"Collected {len(all_tracks)} unique tracks", 18)

    # Step 2: Enrich
    seed_genres: dict = {}
    for _a in top_artists_list:
        if _a.get("id"):
            seed_genres[_a["id"]] = _a.get("genres") or []

    _nonempty_seeds = sum(1 for g in seed_genres.values() if g)
    print(f"  Genre seed            {len(seed_genres)} artists ({_nonempty_seeds} with genres)")

    step(f"Fetching genre data for {len(all_tracks)} tracks...", 22)
    artist_genres_map, audio_features_map = enrich.gather(sp, all_tracks, seed_genres=seed_genres)

    _has_audio = bool(
        audio_features_map
        and any(v for v in audio_features_map.values() if v)
    )
    _has_genres = any(v for v in artist_genres_map.values() if v)
    _nonempty_g = sum(1 for v in artist_genres_map.values() if v)
    step(f"Enrichment done — {_nonempty_g}/{len(artist_genres_map)} artists with genres", 38)

    # Step 3: Playlist mining
    moods = all_moods()
    user_uris = {t["uri"] for t in all_tracks if t.get("uri")}
    step("Running playlist mining (first run ~30s, then cached)...", 42)
    mining = playlist_mining.mine(
        sp,
        user_uris,
        moods,
        playlists_per_seed=cfg.PLAYLISTS_PER_SEED,
        force_refresh=force_refresh or cfg.MINING_FORCE_REFRESH,
        max_tracks_per_playlist=getattr(cfg, "MINING_MAX_TRACKS_PER_PLAYLIST", 100),
        user_tracks=all_tracks,
    )
    track_tags = mining.get("track_tags", {})
    mood_fit_playlists = mining.get("mood_fit_playlists", {})
    track_context = mining.get("track_context", {})
    mining_blocked = mining.get("blocked", False)
    playlist_items_blocked = mining.get("playlist_items_blocked", mining_blocked)
    if mining_blocked or playlist_items_blocked:
        _lf_key_present = bool(
            getattr(cfg, "VIBESORT_LASTFM_API_KEY", "").strip()
            or getattr(cfg, "LASTFM_API_KEY", "").strip()
        )
        _fallback_label = "Last.fm" if _lf_key_present else "MusicBrainz"
        step(f"Playlist mining limited (Spotify Dev Mode) — enriching via {_fallback_label}...", 48)
    else:
        step(f"Playlist mining complete — {len(track_tags)} tags collected", 48)

    _mining_degraded = bool(mining_blocked or playlist_items_blocked)
    _tagged_n = sum(1 for u in user_uris if track_tags.get(u))
    if user_uris and (_tagged_n / len(user_uris)) < 0.10:
        _mining_degraded = True
    _enrich_mult = (
        float(getattr(cfg, "MINING_FALLBACK_ENRICH_MULT", 1.65)) if _mining_degraded else 1.0
    )
    if _mining_degraded and _enrich_mult > 1.01:
        step(
            f"Boosting free/API enrichment (×{_enrich_mult:.2f}) — thin playlist-mining signal",
            49,
        )

    _lf_key = (
        getattr(cfg, "VIBESORT_LASTFM_API_KEY", "").strip()
        or getattr(cfg, "LASTFM_API_KEY", "").strip()
    )
    if _lf_key:
        try:
            from core import lastfm as _lf_mod
            _lf_stats = _lf_mod.cache_stats()
            _cached_a = _lf_stats.get("artists_cached", 0)
            _cached_t = _lf_stats.get("tracks_cached", 0)
            _cache_note = (
                f" ({_cached_a} artists / {_cached_t} tracks cached)"
                if (_cached_a or _cached_t)
                else " (first run — building cache)"
            )
            step(f"Enriching via Last.fm{_cache_note}...", 50)

            def _lf_progress(msg: str):
                step(msg, 55)

            # M1.7: removed per-track cap — full library enriched; cache makes
            # rescans instant (only uncached tracks incur API calls).
            _lf_cap = len(all_tracks)   # no cap; was max(300, min(1000, N))
            _n_tracks = len(all_tracks)
            _est_first = max(1, _n_tracks - len(
                [t for t in all_tracks
                 if _lf_mod._load_cache().get("tracks", {}).get(
                     f"{('_'.join((t.get('artists') or [{}])[0].get('name','').lower().split()))}|||"
                     f"{'_'.join(t.get('name','').lower().split())}"
                 )]
            ))
            if _est_first > 0:
                _est_min = max(1, (_est_first * 21) // 60)
                step(
                    f"Last.fm track tags   {_est_first} uncached tracks (~{_est_min} min"
                    f" first run; cached permanently after)", 55
                )
            _lf_artist_tags, _lf_track_tags = _lf_mod.enrich_library(
                all_tracks,
                _lf_key,
                max_artists=_lf_cap,
                max_tracks=_lf_cap,
                progress_fn=_lf_progress,
            )

            _lf_genres_added = 0
            for _aid, _raw_tags in _lf_artist_tags.items():
                if not artist_genres_map.get(_aid) and _raw_tags:
                    artist_genres_map[_aid] = _raw_tags
                    _lf_genres_added += 1

            _lf_tracks_added = 0
            for _uri, _tags in _lf_track_tags.items():
                if not _tags:
                    continue
                if _uri not in track_tags:
                    track_tags[_uri] = _tags
                    _lf_tracks_added += 1
                else:
                    _merged = dict(_tags)
                    _merged.update(track_tags[_uri])
                    track_tags[_uri] = _merged

            _has_genres = any(v for v in artist_genres_map.values() if v)
            step(
                f"Last.fm done — {_lf_genres_added} artists + {_lf_tracks_added} tracks enriched",
                58,
            )
        except Exception as _lf_err:
            step(f"Last.fm enrichment failed: {_lf_err}", 58)

    elif not _lf_key:
        try:
            from core import deezer as _dz_mod

            _dz_stats = _dz_mod.cache_stats()
            _dz_cached = _dz_stats.get("artists_cached", 0)
            _dz_note = (
                f" ({_dz_cached} artists cached)" if _dz_cached else " (first run — building cache, ~60s)"
            )
            step(f"Enriching artist genres via Deezer{_dz_note}...", 50)

            _dz_artist_freq: dict = {}
            for _t in all_tracks:
                for _a in _t.get("artists", []):
                    _aid = _a.get("id", "")
                    _aname = _a.get("name", "")
                    if _aid and _aname:
                        _prev = _dz_artist_freq.get(_aid, (_aname, 0))[1]
                        _dz_artist_freq[_aid] = (_aname, _prev + 1)

            def _dz_progress(msg: str):
                step(msg, 54)

            _dz_result = _dz_mod.enrich_artists(
                _dz_artist_freq,
                existing_genres=artist_genres_map,
                max_artists=min(900, int(300 * _enrich_mult)),
                progress_fn=_dz_progress,
            )

            _dz_added = 0
            for _aid, _genres in _dz_result.items():
                if not artist_genres_map.get(_aid) and _genres:
                    artist_genres_map[_aid] = _genres
                    _dz_added += 1

            _has_genres = any(v for v in artist_genres_map.values() if v)
            step(f"Deezer done — {_dz_added} artists with genre data", 57)

        except Exception as _dz_err:
            step(f"Deezer enrichment failed: {_dz_err}", 57)

        step(f"Enrichment complete — {len(track_tags)} tracks tagged via Deezer", 59)

    _dz_need = [aid for aid, g in artist_genres_map.items() if not g]
    if _dz_need:
        try:
            from core import deezer as _dz_gap
            _dz_gfreq: dict = {}
            for _gt in all_tracks:
                for _ga in _gt.get("artists", []):
                    _gaid = _ga.get("id", "")
                    _ganame = _ga.get("name", "")
                    if _gaid and _ganame and not artist_genres_map.get(_gaid):
                        _gprev = _dz_gfreq.get(_gaid, (_ganame, 0))[1]
                        _dz_gfreq[_gaid] = (_ganame, _gprev + 1)
            if _dz_gfreq:
                _dz_gcached = _dz_gap.cache_stats().get("artists_cached", 0)
                _dz_gnote = (
                    f" ({_dz_gcached} artists cached)" if _dz_gcached else " (first run — building cache, ~60s)"
                )
                step(f"Deezer genre gap-fill{_dz_gnote}...", 60)
                _dz_gresult = _dz_gap.enrich_artists(
                    _dz_gfreq,
                    existing_genres=artist_genres_map,
                    max_artists=min(1000, int(600 * _enrich_mult)),
                    progress_fn=lambda m: step(m, 61),
                )
                _dz_gadded = 0
                for _gaid, _ggenres in _dz_gresult.items():
                    if _ggenres and not artist_genres_map.get(_gaid):
                        artist_genres_map[_gaid] = _ggenres
                        _dz_gadded += 1
                if _dz_gadded:
                    _has_genres = True
                step(f"Deezer gap-fill — {_dz_gadded} artists enriched", 62)
        except Exception as _dz_gerr:
            step(f"Deezer gap-fill skipped: {_dz_gerr}", 62)

    # ── MusicBrainz track-tag gap-fill (universal) ────────────────────────────
    # Runs regardless of Last.fm key, for any tracks still missing tags.
    # Conditions: either MUSICBRAINZ_ENRICH flag is set, OR coverage is very low
    # (< 40% of tracks tagged after all primary sources).
    _mb_uncovered = [t for t in all_tracks if not track_tags.get(t.get("uri", ""))]
    _mb_coverage = 1.0 - (len(_mb_uncovered) / max(len(all_tracks), 1))
    _mb_run = getattr(cfg, "MUSICBRAINZ_ENRICH", False) or (
        _mb_coverage < (0.52 if _mining_degraded else 0.40) and not _lf_key
    ) or (_mining_degraded and _mb_coverage < 0.68)
    if _mb_run and _mb_uncovered:
        try:
            from core import musicbrainz as _mb_mod
            _mb_base = 200 if getattr(cfg, "MUSICBRAINZ_ENRICH", False) else 100
            _mb_cap = min(450, int(_mb_base * _enrich_mult))
            _mb_sorted = sorted(_mb_uncovered, key=lambda t: -t.get("popularity", 0))
            _mb_note = (
                f"{min(len(_mb_sorted), _mb_cap)} uncovered tracks"
                f" — {'explicit' if getattr(cfg, 'MUSICBRAINZ_ENRICH', False) else 'auto'}"
            )
            step(f"MusicBrainz tag gap-fill ({_mb_note}, first run ~3 min)...", 62)
            _mb_gap_result = _mb_mod.enrich_tracks(_mb_sorted, max_tracks=_mb_cap)
            _mb_gap_added = 0
            for _mb_uri, _mb_tags in _mb_gap_result.items():
                if not _mb_tags:
                    continue
                if _mb_uri not in track_tags:
                    track_tags[_mb_uri] = _mb_tags
                    _mb_gap_added += 1
                else:
                    _merged = dict(_mb_tags)
                    _merged.update(track_tags[_mb_uri])
                    track_tags[_mb_uri] = _merged
            step(f"MusicBrainz gap-fill — {_mb_gap_added} tracks tagged", 63)
        except ImportError:
            step("MusicBrainz skipped (musicbrainzngs not installed)", 63)
        except Exception as _mb_gap_err:
            step(f"MusicBrainz gap-fill failed: {_mb_gap_err}", 63)

    # ── MusicBrainz artist-genre last resort ──────────────────────────────────
    # For artists still missing genres after Spotify + Last.fm + Deezer.
    # Uses musicbrainz.artist_tags() which was previously dead code.
    _mb_genre_gaps = [
        (_aid, next(
            (_a.get("name", "") for _t in all_tracks
             for _a in _t.get("artists", []) if _a.get("id") == _aid),
            "",
        ))
        for _aid, _g in artist_genres_map.items()
        if not _g
    ]
    if _mb_genre_gaps:
        try:
            from core import musicbrainz as _mb_art
            _mb_art_cap = min(120, int(60 * _enrich_mult))
            _mb_art_added = 0
            for _gaid, _ganame in _mb_genre_gaps[:_mb_art_cap]:
                if not _ganame:
                    continue
                _mb_atags = _mb_art.artist_tags(_ganame)
                if _mb_atags:
                    artist_genres_map[_gaid] = [t.replace("_", " ") for t in _mb_atags.keys()]
                    _mb_art_added += 1
            if _mb_art_added:
                _has_genres = True
                step(f"MusicBrainz artist genres — {_mb_art_added} artists filled", 64)
        except ImportError:
            pass
        except Exception as _mb_art_err:
            step(f"MusicBrainz artist genre fill failed: {_mb_art_err}", 64)

    # Artist frequency map for AudioDB + Discogs (must exist even if AudioDB fails)
    _adb_artist_freq: dict = {}
    for _t in all_tracks:
        for _a in _t.get("artists", []):
            _aid = _a.get("id", "")
            _aname = _a.get("name", "")
            if _aid and _aname:
                _prev = _adb_artist_freq.get(_aid, (_aname, 0))[1]
                _adb_artist_freq[_aid] = (_aname, _prev + 1)

    # ── TheAudioDB enrichment ─────────────────────────────────────────────────
    # Free, no key, editorial-quality mood/genre labels per artist and track.
    # Single unified pass: one API call per artist (genres + mood together),
    # then artist mood is broadcast to all tracks, then track-level pass for
    # tracks still missing signal. Total: ~150+100 calls at 0.35s ≈ 90s max.
    try:
        from core import audiodb as _adb_mod
        _adb_stats = _adb_mod.cache_stats()
        _adb_cached = _adb_stats.get("artists_cached", 0) + _adb_stats.get("tracks_cached", 0)
        _adb_note = f" ({_adb_cached} cached)" if _adb_cached else " (first run — up to 90s)"
        step(f"Enriching via TheAudioDB{_adb_note}...", 65)

        _adb_genre_result, _adb_track_result = _adb_mod.enrich_library(
            all_tracks,
            _adb_artist_freq,
            existing_genres=artist_genres_map,
            existing_tags=track_tags,
            max_artists=min(380, int(150 * _enrich_mult)),
            # max_tracks omitted → None (no cap); cache is permanent so
            # previously-fetched tracks cost 0 API calls on re-runs.
            progress_fn=lambda m: step(m, 67),
        )

        _adb_genre_added = 0
        for _aid, _genres in _adb_genre_result.items():
            if not artist_genres_map.get(_aid) and _genres:
                artist_genres_map[_aid] = _genres
                _adb_genre_added += 1
        if _adb_genre_added:
            _has_genres = True

        _adb_track_added = 0
        for _uri, _tags in _adb_track_result.items():
            if not _tags:
                continue
            if _uri not in track_tags:
                track_tags[_uri] = _tags
                _adb_track_added += 1
            else:
                for _tg, _tw in _tags.items():
                    if _tg not in track_tags[_uri]:
                        track_tags[_uri][_tg] = _tw

        step(
            f"AudioDB done — {_adb_genre_added} artist genres · "
            f"{_adb_track_added} tracks tagged",
            69,
        )
    except Exception as _adb_err:
        step(f"AudioDB enrichment skipped: {_adb_err}", 69)

    # ── Discogs sub-genre style enrichment (no key required) ─────────────────
    # Discogs gives precise sub-genre style labels that Deezer lacks:
    #   "Cloud Rap", "Shoegaze", "Trip-Hop", "Neo Soul", "Grunge", etc.
    # These feed both macro genre placement AND mood tag vocabulary.
    # Rate: 25 req/min (free) → ~120 artists in ~5 min, cached forever after.
    _dc_token = getattr(cfg, "DISCOGS_TOKEN", "").strip()  # optional, raises limit to 60/min
    _has_discogs = False
    try:
        from core import discogs as _dc_mod
        _dc_stats_raw = _dc_mod._load_cache()
        _dc_cached = len(_dc_stats_raw.get("artists", {}))
        _dc_note = f" ({_dc_cached} cached)" if _dc_cached else " (first run — ~5 min)"
        step(f"Enriching via Discogs{_dc_note}...", 70)

        _dc_genre_result, _dc_track_result = _dc_mod.enrich_library(
            all_tracks,
            _adb_artist_freq,
            existing_genres=artist_genres_map,
            existing_tags=track_tags,
            discogs_token=_dc_token,
            max_artists=min(280, int(120 * _enrich_mult)),
            progress_fn=lambda m: step(m, 71),
        )

        _dc_genre_added = 0
        for _aid, _genres in _dc_genre_result.items():
            if _genres:
                artist_genres_map[_aid] = _genres
                _dc_genre_added += 1
        if _dc_genre_added:
            _has_genres = True

        _dc_track_added = 0
        for _uri, _tags in _dc_track_result.items():
            if not _tags:
                continue
            if _uri not in track_tags:
                track_tags[_uri] = _tags
                _dc_track_added += 1
            else:
                for _tg, _tw in _tags.items():
                    if _tg not in track_tags[_uri]:
                        track_tags[_uri][_tg] = _tw
                _dc_track_added += 1

        step(
            f"Discogs done — {_dc_genre_added} artist styles · "
            f"{_dc_track_added} tracks tagged",
            72,
        )
        _has_discogs = True
    except Exception as _dc_err:
        step(f"Discogs enrichment skipped: {_dc_err}", 72)

    # ── Musixmatch per-track genre enrichment (optional, requires free key) ────
    # Trusted professional source (used by Apple Music, Amazon Music, Spotify).
    # Provides per-track genre tags via ISRC lookup — more precise than artist genres.
    # Free tier: 2,000 API calls/day, cached after first run (no repeated calls).
    _mx_key = getattr(cfg, "MUSIXMATCH_API_KEY", "").strip()
    if _mx_key:
        try:
            from core import musixmatch as _mx_mod
            _mx_stats = _mx_mod.cache_stats()
            _mx_cached = _mx_stats.get("tracks_cached", 0)
            _mx_note = f" ({_mx_cached} cached)" if _mx_cached else " (first run)"
            step(f"Enriching via Musixmatch{_mx_note}...", 70)

            _mx_result = _mx_mod.enrich_tracks(
                all_tracks,
                _mx_key,
                max_tracks=min(500, int(300 * _enrich_mult)),
                progress_fn=lambda m: step(m, 71),
            )

            _mx_added = 0
            for _uri, _genres in _mx_result.items():
                if not _genres:
                    continue
                # Musixmatch gives per-track genres; merge into artist_genres_map
                # by finding the primary artist and adding genres to their map.
                _t_obj = next((t for t in all_tracks if t.get("uri") == _uri), None)
                if _t_obj:
                    for _a in (_t_obj.get("artists") or []):
                        _aid = _a.get("id", "")
                        if _aid and not artist_genres_map.get(_aid):
                            artist_genres_map[_aid] = _genres
                            _has_genres = True
                            _mx_added += 1
                            break

            step(f"Musixmatch done — {_mx_added} artists with track-derived genres", 72)
        except Exception as _mx_err:
            step(f"Musixmatch enrichment skipped: {_mx_err}", 72)

    _has_lyrics = False
    _lyrics_lang_map: dict | None = None
    _genius_key = getattr(cfg, "GENIUS_API_KEY", "").strip()
    _has_genius = bool(_genius_key)
    try:
        from core import lyrics as _lyr_mod
        _lyr_tracks = sorted(all_tracks, key=lambda t: -t.get("popularity", 0))
        # M1.7: removed lyrics cap — full library covered; lrclib has no rate limit.
        # Cache is permanent — only uncached tracks incur network calls on rescan.
        _lyr_base = len(all_tracks)   # no cap; was max(200, min(800, N))
        _lyr_max = _lyr_base
        _lyr_cached = sum(
            1
            for t in _lyr_tracks
            if _lyr_mod._load_cache().get(
                _lyr_mod._cache_key(
                    (t.get("artists") or [{}])[0].get("name", "")
                    if isinstance((t.get("artists") or [{}])[0], dict)
                    else (t.get("artists") or [""])[0],
                    t.get("name", ""),
                )
            )
        )
        _lyr_uncached = len(_lyr_tracks) - _lyr_cached
        if _lyr_cached:
            _lyr_note = f" ({_lyr_cached} cached, {_lyr_uncached} to fetch)"
        else:
            _lyr_est_min = max(1, (len(_lyr_tracks) * 25) // 6000)
            _lyr_note = (
                f" (first run — {len(_lyr_tracks)} tracks, ~{_lyr_est_min} min;"
                f" cached permanently after)"
            )
        _lyr_src = (
            "lrclib + lyrics.ovh + Genius"
            if _genius_key
            else "lrclib + lyrics.ovh"
        )
        step(f"Analysing lyrics ({_lyr_src}){_lyr_note}...", 60)
        if _genius_key:
            step("Genius enrichment active (fallback when free sources miss)", 60)

        _lyr_tags_map, _lyr_lang_map = _lyr_mod.enrich_library(
            _lyr_tracks,
            max_tracks=_lyr_max,
            genius_api_key=_genius_key or None,
        )

        _lyr_added = 0
        for _uri, _ltags in _lyr_tags_map.items():
            if not _ltags:
                continue
            if _uri not in track_tags:
                track_tags[_uri] = _ltags
                _lyr_added += 1
            else:
                _merged = dict(_ltags)
                _merged.update(track_tags[_uri])
                track_tags[_uri] = _merged

        if _lyr_lang_map:
            _lyrics_lang_map = _lyr_lang_map
        _has_lyrics = bool(_lyr_added)
        step(f"Lyrics done — {_lyr_added} tracks with lyrical mood scores", 63)
    except Exception as _lyr_err:
        step(f"Lyrics enrichment failed: {_lyr_err}", 63)

    _lb_token = getattr(cfg, "LISTENBRAINZ_TOKEN", "").strip()
    _lb_username = getattr(cfg, "LISTENBRAINZ_USERNAME", "").strip()
    _lb_top_uris: dict[str, float] = {}
    _has_listenbrainz = False

    if _lb_token and _lb_username:
        try:
            from core import listenbrainz as _lb_mod
            _lb_client = _lb_mod.connect(_lb_token)
            if _lb_client:
                step("Fetching ListenBrainz listening history...", 65)
                _lb_tracks = _lb_mod.top_tracks(_lb_client, _lb_username, count=100)
                if _lb_tracks:
                    _lb_lookup: dict[tuple, int] = {}
                    _lb_max_count = max((t.get("listen_count", 1) for t in _lb_tracks), default=1) or 1
                    for _lbt in _lb_tracks:
                        _key = (
                            _lbt.get("artist", "").lower().strip(),
                            _lbt.get("title", "").lower().strip(),
                        )
                        if _key[0] and _key[1]:
                            _lb_lookup[_key] = _lbt.get("listen_count", 1)

                    _lb_matched = 0
                    for _t in all_tracks:
                        _uri = _t.get("uri", "")
                        if not _uri:
                            continue
                        _t_title = _t.get("name", "").lower().strip()
                        for _a in _t.get("artists", []):
                            _t_artist = _a.get("name", "").lower().strip()
                            _lc = _lb_lookup.get((_t_artist, _t_title), 0)
                            if _lc:
                                _norm = _lc / _lb_max_count
                                _lb_top_uris[_uri] = 1.05 + (_norm * 0.15)
                                _lb_matched += 1
                                break

                    _has_listenbrainz = bool(_lb_matched)
                    step(
                        f"ListenBrainz done — {_lb_matched} frequently-played tracks "
                        "will be prioritised in playlists",
                        66,
                    )
                else:
                    step("ListenBrainz: no listening history found", 66)
            else:
                step("ListenBrainz: connection failed (check token)", 66)
        except ImportError:
            step("ListenBrainz: liblistenbrainz not installed — skipping", 66)
        except Exception as _lb_err:
            step(f"ListenBrainz enrichment failed: {_lb_err}", 66)

    # ── Last.fm user boost (loved tracks + personal top tracks) ──────────────
    # If the user is authenticated via Last.fm web-auth, their loved tracks get
    # a fixed 1.15× boost and personal top tracks get up to 1.10× boost.
    # This is merged into the same _lb_top_uris multiplier used by ListenBrainz.
    try:
        from core import lastfm as _lf_user_mod
        _lf_sess = _lf_user_mod.load_session()
        if _lf_sess and _lf_sess.get("key") and _lf_sess.get("name"):
            _lf_sess_key = _lf_sess["key"]
            _lf_sess_user = _lf_sess["name"]
            # resolve active API key (shared app key takes priority)
            _lf_active_key = (
                getattr(cfg, "VIBESORT_LASTFM_API_KEY", "").strip()
                or getattr(cfg, "LASTFM_API_KEY", "").strip()
            )
            if _lf_active_key:
                step(f"Fetching Last.fm loved tracks for {_lf_sess_user}...", 67)

                # Build artist|||title lookup key matching Last.fm normalisation
                _lf_lookup: dict[str, str] = {}  # "artist|||title" → uri
                for _t in all_tracks:
                    _t_uri = _t.get("uri", "")
                    if not _t_uri:
                        continue
                    for _a in (_t.get("artists") or []):
                        _a_name = "_".join(_a.get("name", "").lower().split())
                        _t_name = "_".join(_t.get("name", "").lower().split())
                        if _a_name and _t_name:
                            _lf_lookup[f"{_a_name}|||{_t_name}"] = _t_uri
                            break

                # Loved tracks → 1.15× boost
                _loved = _lf_user_mod.get_user_loved_tracks(
                    _lf_sess_key, _lf_active_key, _lf_sess_user, limit=500
                )
                _loved_matched = 0
                for _lk in _loved:
                    _matched_uri = _lf_lookup.get(_lk)
                    if _matched_uri:
                        _lb_top_uris[_matched_uri] = max(
                            _lb_top_uris.get(_matched_uri, 1.0), 1.15
                        )
                        _loved_matched += 1

                # Top tracks → up to 1.10× boost (normalised play count)
                _lf_top = _lf_user_mod.get_user_top_tracks(
                    _lf_active_key, _lf_sess_user, period="6month", limit=200
                )
                _top_matched = 0
                for _lk, _lw in _lf_top.items():
                    _matched_uri = _lf_lookup.get(_lk)
                    if _matched_uri and _matched_uri not in _lb_top_uris:
                        _lb_top_uris[_matched_uri] = 1.0 + (_lw * 0.10)
                        _top_matched += 1

                if _loved_matched or _top_matched:
                    step(
                        f"Last.fm personal boost — {_loved_matched} loved · "
                        f"{_top_matched} top tracks prioritised",
                        68,
                    )
    except Exception as _lf_user_err:
        step(f"Last.fm personal boost skipped: {_lf_user_err}", 68)

    # ── Maloja play-count boost ───────────────────────────────────────────────
    # Maloja is a self-hosted scrobble server (open-source Last.fm alternative).
    # We use it exactly like ListenBrainz: match top tracks by artist+title and
    # apply a play-count-weighted boost multiplier to _lb_top_uris.
    _maloja_url   = getattr(cfg, "MALOJA_URL",   "").strip()
    _maloja_token = getattr(cfg, "MALOJA_TOKEN", "").strip()
    _has_maloja   = False
    if _maloja_url and _maloja_token:
        try:
            from core import maloja as _maloja_mod
            step("Fetching Maloja listening history...", 69)
            _mj_tracks = _maloja_mod.top_tracks(_maloja_url, _maloja_token, max_tracks=500)
            if _mj_tracks:
                _mj_max = max((t["scrobbles"] for t in _mj_tracks), default=1) or 1
                _mj_lookup: dict[tuple, int] = {
                    (t["artist"].lower().strip(), t["title"].lower().strip()): t["scrobbles"]
                    for t in _mj_tracks
                }
                _mj_matched = 0
                for _t in all_tracks:
                    _uri = _t.get("uri", "")
                    if not _uri:
                        continue
                    _t_title = _t.get("name", "").lower().strip()
                    for _a in _t.get("artists", []):
                        _lc = _mj_lookup.get((_a.get("name", "").lower().strip(), _t_title), 0)
                        if _lc:
                            _norm = _lc / _mj_max
                            _boost = 1.05 + (_norm * 0.15)
                            _lb_top_uris[_uri] = max(_lb_top_uris.get(_uri, 1.0), _boost)
                            _mj_matched += 1
                            break
                _has_maloja = bool(_mj_matched)
                step(f"Maloja done — {_mj_matched} frequently-played tracks prioritised", 69)
            else:
                step("Maloja: no scrobble history found", 69)
        except Exception as _mj_err:
            step(f"Maloja boost skipped: {_mj_err}", 69)

    # ── Bandcamp collection enrichment ───────────────────────────────────────
    # Bandcamp purchases/wishlists give deep underground/indie genre signal.
    _bc_username = getattr(cfg, "BANDCAMP_USERNAME", "").strip()
    if _bc_username:
        try:
            from core import bandcamp as _bc_mod
            step(f"Fetching Bandcamp collection for {_bc_username}...", 70)
            _bc_items = _bc_mod.fetch_collection(_bc_username)
            if _bc_items:
                _bc_artist_tags = _bc_mod.collection_to_artist_tags(_bc_items)
                _bc_added = 0
                for _bc_name, _bc_genres in _bc_artist_tags.items():
                    for _t in all_tracks:
                        for _a in _t.get("artists", []):
                            if _a.get("name", "").lower() == _bc_name:
                                _aid = _a.get("id", "")
                                if _aid and not artist_genres_map.get(_aid):
                                    artist_genres_map[_aid] = _bc_genres
                                    _bc_added += 1
                step(f"Bandcamp done — {len(_bc_items)} items, {_bc_added} artist genres added", 71)
            else:
                step("Bandcamp: no items found (collection may be private)", 71)
        except Exception as _bc_err:
            step(f"Bandcamp enrichment skipped: {_bc_err}", 71)

    # ── beets library enrichment ──────────────────────────────────────────────
    # beets tags are hand-curated — high confidence signal for local libraries.
    _beets_db = getattr(cfg, "BEETS_DB_PATH", "").strip()
    try:
        from core import beets as _beets_mod
        if _beets_mod.is_available(_beets_db or None):
            step("Reading beets music library...", 71)
            _beets_artist_tags, _beets_track_tags_raw = _beets_mod.read_library(_beets_db or None)
            _beets_uri_tags = _beets_mod.match_to_spotify(_beets_track_tags_raw, all_tracks)
            _beets_genre_added = 0
            for _b_name, _b_genres in _beets_artist_tags.items():
                for _t in all_tracks:
                    for _a in _t.get("artists", []):
                        if _a.get("name", "").lower() == _b_name:
                            _aid = _a.get("id", "")
                            if _aid and not artist_genres_map.get(_aid):
                                artist_genres_map[_aid] = _b_genres
                                _beets_genre_added += 1
            _beets_tag_added = 0
            for _uri, _btags in _beets_uri_tags.items():
                if not _btags:
                    continue
                if _uri not in track_tags:
                    track_tags[_uri] = _btags
                    _beets_tag_added += 1
                else:
                    for _k, _v in _btags.items():
                        track_tags[_uri].setdefault(_k, _v)
            step(
                f"beets done — {_beets_genre_added} artist genres · "
                f"{_beets_tag_added} tracks tagged",
                72,
            )
    except Exception as _beets_err:
        step(f"beets enrichment skipped: {_beets_err}", 72)

    # ── RYM export enrichment ─────────────────────────────────────────────────
    # Rate Your Music genre/descriptor data — deepest taxonomy available.
    _rym_path = getattr(cfg, "RYM_EXPORT_PATH", "").strip()
    if _rym_path and os.path.exists(_rym_path):
        try:
            from core import rym as _rym_mod
            step(f"Importing RYM export from {os.path.basename(_rym_path)}...", 73)
            _rym_artist_genres, _rym_track_tags_raw = _rym_mod.parse_export(_rym_path)
            _rym_genre_added = _rym_mod.match_artists_to_spotify(
                _rym_artist_genres, artist_genres_map, all_tracks
            )
            _rym_uri_tags = _rym_mod.match_to_spotify(_rym_track_tags_raw, all_tracks)
            _rym_tag_added = 0
            for _uri, _rtags in _rym_uri_tags.items():
                if not _rtags:
                    continue
                if _uri not in track_tags:
                    track_tags[_uri] = _rtags
                    _rym_tag_added += 1
                else:
                    for _k, _v in _rtags.items():
                        track_tags[_uri].setdefault(_k, _v)
            step(
                f"RYM done — {_rym_genre_added} artist genres · "
                f"{_rym_tag_added} tracks tagged",
                74,
            )
        except Exception as _rym_err:
            step(f"RYM import skipped: {_rym_err}", 74)

    # ── Navidrome / Jellyfin (OpenSubsonic) enrichment ───────────────────────
    # Starred tracks from Navidrome/Jellyfin → 1.15× boost in _lb_top_uris.
    # Artist genres from local file tags fill gaps in artist_genres_map.
    _nd_url   = getattr(cfg, "NAVIDROME_URL",  "").strip()
    _nd_user  = getattr(cfg, "NAVIDROME_USER", "").strip()
    _nd_pass  = getattr(cfg, "NAVIDROME_PASS", "").strip()
    _has_navidrome = False
    if _nd_url and _nd_user and _nd_pass:
        try:
            from core import navidrome as _nd_mod
            step("Fetching Navidrome starred tracks & genres...", 75)
            _nd_starred = _nd_mod.get_starred(_nd_url, _nd_user, _nd_pass)
            if _nd_starred:
                _nd_boosts = _nd_mod.match_to_spotify(_nd_starred, all_tracks)
                for _uri, _boost in _nd_boosts.items():
                    _lb_top_uris[_uri] = max(_lb_top_uris.get(_uri, 1.0), _boost)
                _has_navidrome = bool(_nd_boosts)
                step(f"Navidrome done — {len(_nd_boosts)} starred tracks boosted", 75)
            # Artist genre fill
            _nd_genres = _nd_mod.get_artist_genres(_nd_url, _nd_user, _nd_pass)
            _nd_genre_added = 0
            for _nd_aname, _nd_agenres in _nd_genres.items():
                if not _nd_agenres:
                    continue
                for _t in all_tracks:
                    for _a in _t.get("artists", []):
                        if _a.get("name", "").lower() == _nd_aname:
                            _aid = _a.get("id", "")
                            if _aid and not artist_genres_map.get(_aid):
                                artist_genres_map[_aid] = _nd_agenres
                                _nd_genre_added += 1
            if _nd_genre_added:
                _has_genres = True
                step(f"Navidrome genres — {_nd_genre_added} artists enriched", 76)
        except Exception as _nd_err:
            step(f"Navidrome enrichment skipped: {_nd_err}", 76)

    # ── Plex Media Server enrichment ──────────────────────────────────────────
    # Rated/recently-played tracks from Plex → boost in _lb_top_uris.
    # Artist genre tags from embedded file metadata → fill artist_genres_map.
    _plex_url   = getattr(cfg, "PLEX_URL",   "").strip()
    _plex_token = getattr(cfg, "PLEX_TOKEN", "").strip()
    _has_plex = False
    if _plex_url and _plex_token:
        try:
            from core import plex as _plex_mod
            step("Fetching Plex library tracks & ratings...", 76)
            _plex_tracks = _plex_mod.get_tracks(_plex_url, _plex_token)
            if _plex_tracks:
                _plex_boosts = _plex_mod.match_to_spotify(_plex_tracks, all_tracks)
                for _uri, _boost in _plex_boosts.items():
                    _lb_top_uris[_uri] = max(_lb_top_uris.get(_uri, 1.0), _boost)
                _has_plex = bool(_plex_boosts)
                step(f"Plex done — {len(_plex_boosts)} rated/recent tracks boosted", 77)
            # Artist genre fill from Plex file tags
            _plex_genres = _plex_mod.get_artist_genres(_plex_url, _plex_token)
            _plex_genre_added = 0
            for _px_aname, _px_agenres in _plex_genres.items():
                if not _px_agenres:
                    continue
                for _t in all_tracks:
                    for _a in _t.get("artists", []):
                        if _a.get("name", "").lower() == _px_aname:
                            _aid = _a.get("id", "")
                            if _aid and not artist_genres_map.get(_aid):
                                artist_genres_map[_aid] = _px_agenres
                                _plex_genre_added += 1
            if _plex_genre_added:
                _has_genres = True
                step(f"Plex genres — {_plex_genre_added} artists enriched", 77)
        except Exception as _plex_err:
            step(f"Plex enrichment skipped: {_plex_err}", 77)

    # ── Apple Music XML enrichment ────────────────────────────────────────────
    # Loved/rated/played tracks from the user's Apple Music library export.
    # Pure stdlib — no dependencies. Loved tracks → 1.15×, high play count → up
    # to 1.10×. Genre tags from embedded file metadata fill artist_genres_map.
    _am_xml = getattr(cfg, "APPLE_MUSIC_XML_PATH", "").strip()
    _has_apple_music = False
    try:
        from core import apple_music as _am_mod
        if _am_mod.is_available(_am_xml or None):
            step("Importing Apple Music library...", 78)
            _am_artist_genres, _am_track_info = _am_mod.parse_library(_am_xml or None)
            if _am_track_info:
                _am_boosts = _am_mod.match_to_spotify(_am_track_info, all_tracks)
                for _uri, _boost in _am_boosts.items():
                    _lb_top_uris[_uri] = max(_lb_top_uris.get(_uri, 1.0), _boost)
                _has_apple_music = bool(_am_boosts)
                step(f"Apple Music done — {len(_am_boosts)} loved/rated/played tracks boosted", 78)
            # Genre fill from embedded tags
            _am_genre_added = 0
            for _am_aname, _am_agenres in _am_artist_genres.items():
                if not _am_agenres:
                    continue
                for _t in all_tracks:
                    for _a in _t.get("artists", []):
                        if _a.get("name", "").lower() == _am_aname:
                            _aid = _a.get("id", "")
                            if _aid and not artist_genres_map.get(_aid):
                                artist_genres_map[_aid] = _am_agenres
                                _am_genre_added += 1
            if _am_genre_added:
                _has_genres = True
                step(f"Apple Music genres — {_am_genre_added} artists enriched", 79)
    except Exception as _am_err:
        step(f"Apple Music enrichment skipped: {_am_err}", 79)

    # ── Mood anchor matching (M1.4) — zero-cost, pure dict lookup ────────────
    # data/mood_anchors.json contains curated known tracks per mood.
    # Any library track matching an anchor (artist + title, case-insensitive,
    # feat.-stripped) gets anchor_<moodname>: 1.0 — highest-confidence signal.
    try:
        from core.anchors import load_mood_anchors, build_anchor_lookup, apply_anchor_tags
        _mood_anchors = load_mood_anchors()
        if _mood_anchors:
            _anchor_lookup = build_anchor_lookup(_mood_anchors)
            _anchor_matched = apply_anchor_tags(all_tracks, track_tags, _anchor_lookup)
            if _anchor_matched:
                step(f"Anchor tags applied — {_anchor_matched} (track, mood) matches", 80)
        else:
            step("Mood anchors not yet populated (run scripts/generate_anchors.py)", 80)
    except Exception as _anc_err:
        step(f"Anchor matching skipped: {_anc_err}", 80)

    # ── Track metadata signals (M1.5) — zero API calls, 100% coverage ───────
    # Extract structural and title-keyword signals from the Spotify track object.
    # Runs in under 1s for any library size. Fills gaps where no enrichment hit.
    try:
        _meta_tags = enrich.enrich_metadata(all_tracks)
        _meta_added = 0
        for _uri, _msigs in _meta_tags.items():
            if _msigs:
                if _uri not in track_tags:
                    track_tags[_uri] = _msigs
                    _meta_added += 1
                else:
                    for _mtag, _mw in _msigs.items():
                        track_tags[_uri].setdefault(_mtag, _mw)
        step(f"Metadata signals applied — {_meta_added} tracks gained first coverage", 81)
    except Exception as _meta_err:
        step(f"Metadata signals skipped: {_meta_err}", 81)

    _has_tags = bool(track_tags)
    _has_genres = any(v for v in artist_genres_map.values() if v)

    _w_tags = float(getattr(cfg, "W_TAGS", 0.46))
    _w_sem = float(getattr(cfg, "W_SEMANTIC", 0.26))
    _w_gen = float(getattr(cfg, "W_GENRE", 0.18))
    _w_proxy = float(getattr(cfg, "W_METADATA_AUDIO", 0.10))
    if _has_genres and _has_tags:
        _weights = (_w_proxy, _w_tags, _w_sem, _w_gen)
    elif _has_tags:
        _s = _w_tags + _w_sem
        if _s > 0:
            _k = 1.0 / _s
            _weights = (_w_proxy, _w_tags * _k, _w_sem * _k, 0.0)
        else:
            _weights = (_w_proxy, 0.70, 0.30, 0.0)
    elif _has_genres:
        _weights = (_w_proxy, 0.0, 0.0, 1.0)
    else:
        _s2 = _w_tags + _w_sem
        if _s2 > 0:
            _k2 = 1.0 / _s2
            _weights = (_w_proxy, _w_tags * _k2, _w_sem * _k2, 0.0)
        else:
            _weights = (_w_proxy, 0.50, 0.50, 0.0)

    _weights = scorer.resolved_score_weights(_weights)

    # ── Semantic expansion pass (enrichment-only tracks) ──────────────────────
    # Mining tracks already went through _apply_semantic_expansion in
    # playlist_mining.mine().  Tracks enriched ONLY via Last.fm/AudioDB/Discogs
    # skipped that pass, so a track tagged "metal" never got implied dims
    # ["anger", "hype", "dark"] added.  Run a final expansion over ALL track_tags
    # now — the function is idempotent (implied tags not set if already stronger).
    from core.playlist_mining import _apply_semantic_expansion as _sem_expand
    from core.profile import collapse_tags as _collapse_for_expansion

    _expanded_n = 0
    for _exp_uri, _exp_tags in track_tags.items():
        if not _exp_tags:
            continue
        _exp_result = _sem_expand(_exp_tags)
        if len(_exp_result) > len(_exp_tags):
            # New implied dims were added — merge cluster names too
            _exp_clusters = _collapse_for_expansion(_exp_result)
            track_tags[_exp_uri] = {**_exp_result, **_exp_clusters} if _exp_clusters else _exp_result
            _expanded_n += 1
    if _expanded_n:
        step(f"Semantic expansion — {_expanded_n} track tag sets enriched with implied dims", 61)

    # ── Tag-derived genre backfill ───────────────────────────────────────────────
    # Artists with no genre data (Spotify/Deezer/Discogs/AudioDB all missed them)
    # often have genre-like tags from Last.fm / AudioDB tags (e.g. "hip-hop", "pop",
    # "rock").  Add those tag keys to artist_genres_map so to_macro() can categorise
    # them, shrinking the "Other" bucket on the Genres/Stats pages.
    # NOTE: This must run BEFORE the audio proxy so the proxy has the correct
    # macro genres for artists that only have tag-derived genre data.
    _artists_without_genres: dict[str, set] = {}
    for _bt in all_tracks:
        _buri = _bt.get("uri", "")
        _btags = track_tags.get(_buri) or {}
        if not _btags:
            continue
        for _ba in _bt.get("artists", []):
            _baid = _ba.get("id", "")
            if _baid and not artist_genres_map.get(_baid):
                if _baid not in _artists_without_genres:
                    _artists_without_genres[_baid] = set()
                _artists_without_genres[_baid].update(_btags.keys())
    _backfilled_n = 0
    for _baid, _btag_keys in _artists_without_genres.items():
        _synthesised = list(_btag_keys)
        if _synthesised:
            artist_genres_map[_baid] = _synthesised
            _backfilled_n += 1
    if _backfilled_n:
        step(f"Genre backfill — {_backfilled_n} artists enriched from tags (reduces 'Other')", 62)

    # ── Audio proxy (runs AFTER genre backfill so proxy has correct macro genres)
    from core import audio_proxy as _audio_proxy_mod

    _proxy_n = _audio_proxy_mod.merge_proxy_into_audio_map(
        all_tracks,
        artist_genres_map,
        track_tags,
        audio_features_map,
    )
    if _proxy_n:
        step(f"Metadata audio proxy — {_proxy_n} tracks (tags/genres heuristics)", 61)

    step("Building track profiles...", 62)
    profiles = profile_mod.build_all(all_tracks, artist_genres_map, audio_features_map, track_tags)
    step(f"Built {len(profiles)} track profiles", 68)

    user_mean = profile_mod.user_audio_mean(profiles)
    user_tag_prefs = profile_mod.user_tag_preferences(profiles)

    step("Analyzing genre, era, and artist patterns...", 70)
    genre_map = genre_mod.library_genre_breakdown(all_tracks, artist_genres_map)
    era_map = genre_mod.era_breakdown(all_tracks)
    artist_map = genre_mod.artist_breakdown(all_tracks, cfg.MIN_SONGS_PER_ARTIST)

    step(f"Scoring {len(moods)} moods against your library...", 75)

    _aw, _tw, _sw = scorer.cohesion_signal_weights(profiles)

    _NICHE_MOODS_GENRE_GATE = 3

    def _library_genre_count(mood_nm: str) -> int:
        pref = scorer.mood_preferred_genres(mood_nm)
        if not pref:
            return _NICHE_MOODS_GENRE_GATE
        return sum(
            1 for p in profiles.values() if any(g in pref for g in p.get("macro_genres", []))
        )

    mood_results: dict = {}
    for mood_name in moods:
        if _has_genres and _library_genre_count(mood_name) < _NICHE_MOODS_GENRE_GATE:
            continue

        _min_score = (
            0.08
            if (_has_tags and _has_genres)
            else 0.10
            if _has_tags
            else 0.50
            if _has_genres
            else 0.15
        )
        _observed_mining = playlist_mining.mood_observed_tag_weights(track_context, mood_name)
        _merged_expected = scorer.combine_expected_tags(mood_name, _observed_mining)

        ranked = scorer.rank_tracks(
            profiles,
            mood_name,
            user_mean,
            user_tag_prefs=user_tag_prefs,
            min_score=_min_score if min_score_override is None else min_score_override,
            weights=_weights,
            min_playlist_size=_mvp_n,
            allow_mvp_fallback=_allow_mvp,
            mvp_score_floor=_mvp_floor,
            merged_expected_tags=_merged_expected,
        )
        if not ranked:
            continue
        all_scored = list(ranked)

        pool_n = max(_max_tracks_cap * 2, 30)
        pool = ranked[:pool_n]
        cohesion_pass = scorer.cohesion_filter(
            pool,
            profiles,
            mood_name,
            threshold=None,
            audio_weight=_aw,
            tag_weight=_tw,
            semantic_weight=_sw,
        )

        if len(cohesion_pass) >= 5:
            trimmed = cohesion_pass[:_max_tracks_cap]
        else:
            trimmed = ranked[:_max_tracks_cap]

        # Artist diversity — without audio features tags are artist-level signals,
        # so one artist dominates. Cap at 3 tracks per artist per playlist.
        _max_artist = int(getattr(cfg, "MAX_TRACKS_PER_ARTIST", 3))
        trimmed = scorer.enforce_artist_diversity(trimmed, profiles, max_per_artist=_max_artist)

        c_raw = cohesion_mod.cohesion_score([u for u, _ in trimmed], profiles)

        if len(trimmed) < 5:
            continue

        _uri_to_score = {uri: sc for uri, sc in ranked}
        _seen: set = set()
        _filtered_ranked = []
        for uri, sc in trimmed:
            if uri not in _seen:
                _seen.add(uri)
                _filtered_ranked.append((uri, _uri_to_score.get(uri, sc)))

        _filtered_ranked = scorer.refine_playlist(_filtered_ranked, drop_ratio=_drop_ratio)
        _filtered_ranked = scorer.ensure_minimum(
            _filtered_ranked,
            all_scored,
            min_tracks=_ensure_target,
            min_score=_min_score if min_score_override is None else min_score_override,
            strict_backfill=_strict_backfill,
            mood_name=mood_name,
            profiles=profiles,
            backfill_expected_tags=_merged_expected,
        )
        # Re-enforce artist cap after backfill — ensure_minimum pulls from all_scored
        # without checking per-artist limits, causing single-artist dominance
        # (e.g. Linkin Park x11 in Hard Reset, Kanye West x14 in Songs About Home).
        _filtered_ranked = scorer.enforce_artist_diversity(
            _filtered_ranked, profiles, max_per_artist=_max_artist
        )

        _avg_sc = (
            sum(sc for _, sc in _filtered_ranked) / len(_filtered_ranked) if _filtered_ranked else 0.0
        )
        _confidence = round(0.7 * c_raw + 0.3 * _avg_sc, 4)

        _tag_agg: dict = {}
        for _uri, _sc in _filtered_ranked:
            for _tag, _tw in track_tags.get(_uri, {}).items():
                _tag_agg[_tag] = _tag_agg.get(_tag, 0.0) + float(_tw) * _sc
        _top_tags = [t for t, _ in sorted(_tag_agg.items(), key=lambda x: -x[1])[:8]]

        mood_results[mood_name] = {
            "ranked": _filtered_ranked,
            "uris": [uri for uri, _ in _filtered_ranked],
            "cohesion": _confidence,
            "count": len(_filtered_ranked),
            "top_tags": _top_tags,
        }

    if _lb_top_uris:
        _lb_boosted: dict = {}
        for _mn, _md in mood_results.items():
            _boosted_ranked = [
                (uri, sc * _lb_top_uris.get(uri, 1.0)) for uri, sc in _md["ranked"]
            ]
            _boosted_ranked.sort(key=lambda x: -x[1])
            _lb_boosted[_mn] = {
                **_md,
                "ranked": _boosted_ranked,
                "uris": [u for u, _ in _boosted_ranked],
            }
        mood_results = _lb_boosted

    _MAX_PL = 3
    _track_best: dict[str, list[tuple[str, float]]] = {}
    for _mn, _md in mood_results.items():
        for _uri, _sc in _md.get("ranked", []):
            _track_best.setdefault(_uri, []).append((_mn, _sc))

    _track_keep: dict[str, set[str]] = {
        _uri: {m for m, _ in sorted(apps, key=lambda x: -x[1])[:_MAX_PL]}
        for _uri, apps in _track_best.items()
    }

    _deduped: dict = {}
    for _mn, _md in mood_results.items():
        _kept_uris = [u for u in _md["uris"] if _mn in _track_keep.get(u, set())]
        if len(_kept_uris) >= 5:
            _deduped[_mn] = {**_md, "uris": _kept_uris, "count": len(_kept_uris)}
    mood_results = _deduped

    _fill_floor = max(int(getattr(cfg, "MIN_PLAYLIST_TOTAL", 25)), min(playlist_min_size, _max_tracks_cap))
    _refilled: dict = {}
    for _mn, _md in mood_results.items():
        uris = list(_md["uris"])
        if len(uris) >= _fill_floor:
            _refilled[_mn] = _md
            continue
        ranked_full = _md.get("ranked", [])
        _seen_u = set(uris)
        for u, _sc in ranked_full:
            if len(uris) >= _fill_floor:
                break
            if u not in _seen_u:
                _seen_u.add(u)
                uris.append(u)
        if len(uris) >= 5:
            _refilled[_mn] = {**_md, "uris": uris, "count": len(uris)}
    mood_results = _refilled

    observed_mood_tags: dict = {}
    for _mn, _md in mood_results.items():
        _tag_agg = {}
        for _uri, _sc in _md.get("ranked", []):
            for _tag, _w in track_tags.get(_uri, {}).items():
                _tag_agg[_tag] = _tag_agg.get(_tag, 0.0) + float(_w) * _sc
        if _tag_agg:
            observed_mood_tags[_mn] = _tag_agg

    step(f"Found {len(mood_results)} vibes in your library", 90)

    history_entries = history_parser.load("data")
    history_stats = history_parser.stats(history_entries) if history_entries else {}
    history_uris = history_parser.sorted_uris(history_entries) if history_entries else []

    step("Scan complete.", 100)

    # Spotify artist popularity (0–100) — public field; complements track popularity for "obscurity"
    artist_popularity: dict[str, int] = {}
    try:
        _aids: list[str] = []
        _seen_aid: set[str] = set()
        for _t in all_tracks:
            for _a in (_t.get("artists") or [])[:2]:
                if isinstance(_a, dict):
                    _aid = _a.get("id") or ""
                    if _aid and _aid not in _seen_aid:
                        _seen_aid.add(_aid)
                        _aids.append(_aid)
        for _i in range(0, min(len(_aids), 400), 50):
            _batch = _aids[_i : _i + 50]
            try:
                _resp = sp.artists(_batch)
                for _art in (_resp or {}).get("artists") or []:
                    if _art and _art.get("id"):
                        artist_popularity[_art["id"]] = int(_art.get("popularity") or 0)
            except Exception:
                break
    except Exception:
        artist_popularity = {}

    try:
        from core import telemetry as _tel

        _tel.log_event(
            "scan_complete",
            n_tracks=len(all_tracks),
            n_moods=len(mood_results),
            corpus_mode=corpus_mode,
        )
    except Exception:
        pass

    payload = {
        "sp": sp,
        "user_id": user_id,
        "all_tracks": all_tracks,
        "top_tracks": top_tracks_list,
        "top_artists": top_artists_list,
        "profiles": profiles,
        "user_mean": user_mean,
        "artist_genres": artist_genres_map,
        "audio_features": audio_features_map,
        "track_tags": track_tags,
        "mood_fit_playlists": mood_fit_playlists,
        "mining_blocked": mining_blocked,
        "playlist_items_blocked": playlist_items_blocked,
        "user_tag_prefs": user_tag_prefs,
        "genre_map": genre_map,
        "era_map": era_map,
        "artist_map": artist_map,
        "mood_results": mood_results,
        "observed_mood_tags": observed_mood_tags,
        "history_stats": history_stats,
        "history_uris": history_uris,
        "existing_uris": user_uris,
        "scan_flags": {
            "has_audio": _has_audio,
            "has_tags": _has_tags,
            "has_genres": _has_genres,
            "has_lyrics": _has_lyrics,
            "has_listenbrainz": _has_listenbrainz,
            "has_maloja": _has_maloja,
            "has_navidrome": _has_navidrome,
            "has_plex": _has_plex,
            "has_apple_music": _has_apple_music,
            "has_discogs": _has_discogs,
            "has_genius": _has_genius,
            "weights": _weights,
        },
        "scan_meta": {
            "corpus_mode": corpus_mode,
            "min_playlist_target": _fill_floor,
            "max_tracks_cap": _max_tracks_cap,
        },
        "lyrics_language_map": dict(_lyrics_lang_map) if _lyrics_lang_map else {},
        "artist_popularity": artist_popularity,
    }
    try:
        delattr(cfg, "SCAN_LYRIC_WEIGHT")
    except AttributeError:
        pass

    # ── Auto-save serializable snapshot (so browser refresh doesn't lose scan) ─
    _snapshot_path = os.path.join(_ROOT if "_ROOT" in dir() else os.path.dirname(os.path.abspath(__file__)), "..", "outputs", ".last_scan_snapshot.json")
    try:
        import json as _json
        _SKIP_KEYS = {"sp"}  # spotipy client is not JSON-serializable
        _snap = {}
        for _sk, _sv in payload.items():
            if _sk in _SKIP_KEYS:
                continue
            try:
                _json.dumps(_sv)    # probe serializability
                _snap[_sk] = _sv
            except (TypeError, ValueError):
                pass
        _snap["_snapshot_ts"] = __import__("time").time()
        _snap_dir = os.path.dirname(_snapshot_path)
        os.makedirs(_snap_dir, exist_ok=True)
        # Atomic write: write to temp file then rename so a crash mid-write
        # never leaves a corrupt snapshot on disk.
        _tmp_path = _snapshot_path + ".tmp"
        with open(_tmp_path, "w", encoding="utf-8") as _sf:
            _json.dump(_snap, _sf, ensure_ascii=False)
        os.replace(_tmp_path, _snapshot_path)
    except Exception:
        pass   # never block the return on snapshot failure

    return payload, _lyrics_lang_map
