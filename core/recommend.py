"""
recommend.py — Track recommendations via Last.fm similar tracks + Spotify search.

Spotify's /v1/recommendations endpoint was deprecated in November 2024 and
returns 403 for Development-Mode apps.  We replace it with:

  Primary:   Last.fm track.getSimilar (semantically similar tracks by listener
             behaviour — same genre, mood, era) → sp.search() to resolve each
             to a Spotify URI.

  Fallback:  Last.fm artist.getSimilar → artist.getTopTracks when track
             similarity yields too few candidates (e.g. very new/obscure tracks
             with no Last.fm play history yet).

If no Last.fm API key is configured the function returns an empty list
gracefully — the playlist deploys with library tracks only, no padding.
"""

from __future__ import annotations

import random
import time
import spotipy

from core.mood_graph import mood_audio_target  # noqa: F401 (kept for callers)
from core.cohesion import cohesion_score       # noqa: F401 (kept for callers)


# ── User market cache ─────────────────────────────────────────────────────────
# Lazily fetched from the Spotify token — avoids passing a new argument through
# every caller while ensuring searches respect the user's actual country/market.
_cached_market: str | None = None
_market_fetched: bool = False


def _get_user_market(sp: spotipy.Spotify) -> str | None:
    """Return the user's Spotify country code, cached after first call."""
    global _cached_market, _market_fetched
    if _market_fetched:
        return _cached_market
    try:
        me = sp.current_user()
        _cached_market = (me.get("country") or "").strip() or None
    except Exception:
        _cached_market = None
    finally:
        _market_fetched = True
    return _cached_market


def reset_market_cache() -> None:
    """
    Clear the cached user market so the next call re-fetches from the current
    Spotify session.  Must be called on disconnect / re-login — otherwise a
    second user on the same process inherits the previous user's country code,
    which silently filters out search results not available in their market.
    """
    global _cached_market, _market_fetched
    _cached_market = None
    _market_fetched = False


# ── Spotify track search (session-scoped in-memory cache) ─────────────────────
# Avoids duplicate sp.search() calls when the same Last.fm similar track
# appears across multiple seed lookups in one recommendations pass.
_search_cache: dict[str, str | None] = {}

_SEARCH_SLEEP = 0.08  # 80 ms between Spotify search calls (~12 req/s)


def _spotify_search_track(
    sp: spotipy.Spotify,
    artist: str,
    title: str,
    market: str | None = None,
) -> str | None:
    """
    Search Spotify for a track by artist + title.  Returns the URI of the
    top result, or None if no match found or the call fails.

    Results are cached for the duration of the process session so the same
    (artist, title) pair is only looked up once per recommendations pass.
    """
    cache_key = f"{artist.lower().strip()}|||{title.lower().strip()}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    uri: str | None = None
    try:
        q = f"artist:{artist} track:{title}"
        kwargs: dict = {"q": q, "type": "track", "limit": 3}
        if market:
            kwargs["market"] = market
        result = sp.search(**kwargs)
        items = (result.get("tracks") or {}).get("items") or []
        uri = items[0]["uri"] if items else None
        time.sleep(_SEARCH_SLEEP)
    except spotipy.SpotifyException:
        pass
    except Exception:
        pass

    _search_cache[cache_key] = uri
    return uri


# ── Last.fm-based recommendations ────────────────────────────────────────────

def lastfm_recommendations(
    sp: spotipy.Spotify,
    seed_uris: list[str],
    profiles: dict[str, dict],
    n: int = 30,
    lastfm_api_key: str = "",
    existing_uris: set[str] | None = None,
) -> list[str]:
    """
    Build a recommendation pool via Last.fm similar tracks + Spotify search.

    Replaces the deprecated Spotify /v1/recommendations endpoint.

    Strategy
    --------
    Pass 1 — track.getSimilar for each seed (up to 5 random seeds):
        Each seed's artist + title is looked up in Last.fm.  For every similar
        track returned, sp.search() resolves it to a Spotify URI.  Results are
        scored by Last.fm match score and deduplicated.

    Pass 2 — artist.getSimilar fallback (runs only when Pass 1 yields < n URIs):
        For each seed's primary artist, fetch similar artists, then pull their
        top tracks and resolve those via sp.search().  Scored at 50 % of the
        artist match score (lower confidence than direct track similarity).

    Args:
        sp:              Authenticated Spotipy client.
        seed_uris:       Track URIs to seed from (library tracks in the playlist).
        profiles:        {uri: profile} for the full library (provides artist/title
                         so we avoid extra Spotify API calls for seed metadata).
        n:               Target pool size (we'll try to return at least n URIs).
        lastfm_api_key:  Last.fm API key.  Returns [] immediately if empty.
        existing_uris:   URIs already in the user's library (filtered out).

    Returns:
        List of Spotify URIs sorted by Last.fm match score, up to n entries.
        Returns [] when no key is configured or no candidates were found.
    """
    if not seed_uris or not lastfm_api_key or n == 0:
        return []

    existing = existing_uris or set()
    market = _get_user_market(sp)

    from core import lastfm as lfm
    cache = lfm._load_cache()

    # Pick up to 5 random seeds for diversity
    pool = seed_uris[:]
    random.shuffle(pool)
    seeds = pool[:5]

    candidates: dict[str, float] = {}  # spotify_uri → best match score seen

    # ── Pass 1: track.getSimilar for each seed ────────────────────────────────
    for seed_uri in seeds:
        prof = profiles.get(seed_uri) or {}
        artist_list = prof.get("artists") or []
        artist = artist_list[0] if artist_list else ""
        title  = prof.get("name", "")

        # If not in profiles (e.g. recs were added from a previous pass), fetch
        # directly from Spotify.
        if not artist or not title:
            try:
                tid = seed_uri.split(":")[-1]
                t = sp.track(tid)
                arts   = t.get("artists") or []
                artist = arts[0].get("name", "") if arts else ""
                title  = t.get("name", "")
            except Exception:
                continue

        if not artist or not title:
            continue

        similar = lfm.get_similar_tracks(
            artist, title, lastfm_api_key,
            limit=max(n * 2, 30),
            cache=cache,
        )
        for sim in similar:
            uri = _spotify_search_track(sp, sim["artist"], sim["title"], market=market)
            if not uri or uri in existing:
                continue
            if candidates.get(uri, -1.0) < sim["match"]:
                candidates[uri] = sim["match"]

    # ── Pass 2: artist.getSimilar fallback when short on candidates ───────────
    if len(candidates) < n:
        seen_artists: set[str] = set()
        for seed_uri in seeds:
            if len(candidates) >= n * 2:
                break
            prof = profiles.get(seed_uri) or {}
            artist_list = prof.get("artists") or []
            artist = artist_list[0] if artist_list else ""
            if not artist or artist.lower() in seen_artists:
                continue
            seen_artists.add(artist.lower())

            sim_artists = lfm.get_similar_artists(
                artist, lastfm_api_key, limit=5, cache=cache
            )
            for sim_art in sim_artists:
                if len(candidates) >= n * 2:
                    break
                top_tracks = lfm.get_artist_top_tracks(
                    sim_art["artist"], lastfm_api_key, limit=3, cache=cache
                )
                for t in top_tracks:
                    uri = _spotify_search_track(
                        sp, t["artist"], t["title"], market=market
                    )
                    if not uri or uri in existing:
                        continue
                    # 50 % confidence discount vs direct track similarity
                    score = sim_art["match"] * 0.5
                    if candidates.get(uri, -1.0) < score:
                        candidates[uri] = score

    lfm._save_cache(cache)

    # Sort by match score descending, return top n
    sorted_uris = sorted(candidates, key=lambda u: -candidates[u])
    return sorted_uris[:n]


# ── filtered_recommendations ──────────────────────────────────────────────────

def filtered_recommendations(
    sp: spotipy.Spotify,
    seed_uris: list[str],
    profiles: dict[str, dict],
    existing_uris: set[str],
    mood_name: str,
    n: int = 15,
    cohesion_threshold: float = 0.55,
    lastfm_api_key: str = "",
) -> tuple[list[str], bool]:
    """
    Fetch, score, and filter recommendations for a playlist.

    Uses Last.fm track.getSimilar + Spotify search as the recommendation
    source (Spotify's /v1/recommendations was deprecated November 2024).

    Pipeline
    --------
    1. Fetch raw candidates via lastfm_recommendations().
    2. Drop tracks already in the user's library.
    3. Fetch Spotify track objects + artist genres (batched).
       No audio-features call — proxy fills via metadata for scoring.
    4. Build a minimal profile for each candidate (profile.build).
    5. Score each profile with scorer.score_track().
    6. Keep tracks with score > 0.15 (hard rejects score -1.0).
    7. cohesion_filter — drop tracks too far from the playlist centroid.
    8. Sort descending by score, return top-n.

    Returns
    -------
    (list[str] of URIs, bool fallback_mode)
    fallback_mode = True when fewer than n tracks survive filtering
    (signals the caller that the playlist couldn't be fully padded).
    On any Spotify API error the function returns (new_recs[:n], True)
    so callers never receive an exception.
    """
    from core import profile as profile_mod
    from core import scorer

    fallback_mode = False

    # ------------------------------------------------------------------
    # Step 1: fetch raw candidates via Last.fm
    # ------------------------------------------------------------------
    raw_recs = lastfm_recommendations(
        sp,
        seed_uris,
        profiles,
        n=n * 2,
        lastfm_api_key=lastfm_api_key,
        existing_uris=existing_uris,
    )

    if not raw_recs:
        return [], True

    # ------------------------------------------------------------------
    # Step 2: drop tracks already in the library
    # ------------------------------------------------------------------
    new_recs = [u for u in raw_recs if u not in existing_uris]
    if not new_recs:
        return [], True

    # ------------------------------------------------------------------
    # Step 3: fetch track objects and artist genres (no audio-features)
    # ------------------------------------------------------------------
    try:
        track_ids = [u.split(":")[-1] for u in new_recs]

        # Track objects (max 50 per call)
        track_map: dict[str, dict] = {}
        for i in range(0, len(track_ids), 50):
            batch = track_ids[i : i + 50]
            result = sp.tracks(batch)
            for t in result.get("tracks") or []:
                if t:
                    track_map[t["id"]] = t
            time.sleep(0.05)

        # Artist genres (max 50 per call)
        artist_ids: list[str] = []
        seen_artists: set[str] = set()
        for t in track_map.values():
            for a in t.get("artists") or []:
                aid = a.get("id")
                if aid and aid not in seen_artists:
                    artist_ids.append(aid)
                    seen_artists.add(aid)

        artist_genres_map: dict[str, list[str]] = {}
        for i in range(0, len(artist_ids), 50):
            batch = artist_ids[i : i + 50]
            result = sp.artists(batch)
            for a in result.get("artists") or []:
                if a:
                    artist_genres_map[a["id"]] = a.get("genres") or []
            time.sleep(0.05)

    except spotipy.SpotifyException as e:
        print(f"    [warn] rec enrichment failed, using raw list: {e}")
        return new_recs[:n], True

    # ------------------------------------------------------------------
    # Steps 4-7: build profiles, score, cohesion-filter, sort
    # ------------------------------------------------------------------
    scored: list[tuple[str, float]] = []
    rec_profiles: dict[str, dict] = {}

    for uri in new_recs:
        tid = uri.split(":")[-1]
        track_obj = track_map.get(tid)
        if not track_obj:
            continue

        # No audio_features_map (deprecated) and no track_tags (rec candidates
        # haven't been through the scan pipeline).  profile.build() will use
        # the metadata-proxy path for the audio vector.
        prof = profile_mod.build(
            track_obj,
            artist_genres_map,
            {},   # audio_features_map — empty; proxy path handles this
            {},   # track_tags — empty for recommendation candidates
        )
        rec_profiles[uri] = prof

        score = scorer.score_track(prof, mood_name)
        if score > 0.15:
            scored.append((uri, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    # Cohesion filter — keep recs close to the playlist centroid
    if len(scored) >= 4:
        cohesion_pass = scorer.cohesion_filter(
            scored,
            rec_profiles,
            mood_name,
            threshold=cohesion_threshold,
        )
        if len(cohesion_pass) >= max(2, n // 3):
            scored = cohesion_pass

    top = [uri for uri, _ in scored[:n]]
    fallback_mode = len(top) < n
    return top, fallback_mode
