"""
recommend.py — Fetch recommendations from Spotify and filter for cohesion.
"""

import random
import time
import spotipy
from core.mood_graph import cosine_similarity, mood_audio_target
from core.cohesion import cohesion_score

# ── User market cache ─────────────────────────────────────────────────────────
# Lazily detected from the Spotify token — avoids threading a new argument
# through every caller while ensuring recommendations respect the user's actual
# country/market (critical for non-US users who would otherwise receive US-only
# recommendations).
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


def spotify_recommendations(
    sp: spotipy.Spotify,
    seed_uris: list[str],
    n: int = 20,
    mood_name: str | None = None,
) -> list[str]:
    """
    Fetch track recommendations from Spotify seeded by up to 5 tracks.
    Uses audio feature targets if mood_name is provided.
    Returns list of track URIs (not in user's existing library).

    Passes the user's own market so that international users receive tracks
    available in their country rather than defaulting to the US catalogue.
    """
    if not seed_uris or n == 0:
        return []

    pool = seed_uris[:]
    random.shuffle(pool)
    seeds = [u.split(":")[-1] for u in pool[:5]]

    kwargs: dict = {"seed_tracks": seeds, "limit": min(n, 100)}

    # Pass user market — without this Spotify defaults to the app's registered
    # country (usually US), silently excluding region-locked tracks for users
    # in MENA, Europe, Asia, Brazil, etc.
    market = _get_user_market(sp)
    if market:
        kwargs["market"] = market

    # Add audio target parameters if we have a mood
    if mood_name:
        target = mood_audio_target(mood_name)
        kwargs["target_energy"]       = target[0]
        kwargs["target_valence"]      = target[1]
        kwargs["target_danceability"] = target[2]
        kwargs["target_acousticness"] = target[4]

    # Spotify returns HTTP 429 when you hit a short-term rate limit ("Too Many Requests").
    # Back off a few seconds and retry — normal API hygiene, not an error code typo.
    _max_attempts = 4
    for attempt in range(_max_attempts):
        try:
            result = sp.recommendations(**kwargs)
            time.sleep(0.14)
            return [t["uri"] for t in result.get("tracks", [])]
        except spotipy.SpotifyException as e:
            if getattr(e, "http_status", None) == 429 and attempt < _max_attempts - 1:
                time.sleep(2.0 + attempt * 2.5)
                continue
            print(f"    [warn] recommendations failed: {e}")
            return []
    return []


def filtered_recommendations(
    sp: spotipy.Spotify,
    seed_uris: list[str],
    profiles: dict[str, dict],
    existing_uris: set[str],
    mood_name: str,
    n: int = 15,
    cohesion_threshold: float = 0.55,
) -> tuple[list[str], bool]:
    """
    Get recommendations, score each candidate against the mood, and return
    the top-n URIs ordered by score.

    Pipeline:
        1. Fetch raw recs from Spotify.
        2. Drop tracks already in the library.
        3. Fetch track objects + audio features + artist genres (batched).
        4. Build a minimal profile for each rec via profile_mod.build().
        5. Score each profile with scorer.score_track().
        6. Keep tracks whose score > 0.15 (hard rejects come back as -1.0).
        7. cohesion_filter — drop tracks too far from the pool's centroid.
        8. Sort descending by score, return top-n URIs.
        9. fallback_mode = True when cohesion_filter left fewer than n tracks
           (signals caller that we couldn't fill the request to full n).

    On any Spotify API error the function falls back to returning new_recs[:n]
    so callers never receive an exception.

    Returns:
        (list[str] of URIs, bool fallback_mode)
    """
    from core import profile as profile_mod  # local import to avoid circular deps
    from core import scorer

    fallback_mode = False

    # ------------------------------------------------------------------
    # Step 1: fetch raw recommendations
    # ------------------------------------------------------------------
    raw_recs = spotify_recommendations(sp, seed_uris, n=n * 2, mood_name=mood_name or None)
    time.sleep(0.12)

    # ------------------------------------------------------------------
    # Step 2: drop tracks already present in the library
    # ------------------------------------------------------------------
    new_recs = [u for u in raw_recs if u not in existing_uris]

    if not new_recs:
        return [], True  # nothing to return — always fallback

    # ------------------------------------------------------------------
    # Step 3: fetch track objects, audio features, and artist genres
    # ------------------------------------------------------------------
    try:
        track_ids = [u.split(":")[-1] for u in new_recs]

        # --- track objects (max 50 per call) ---
        track_map: dict[str, dict] = {}
        for i in range(0, len(track_ids), 50):
            batch = track_ids[i : i + 50]
            result = sp.tracks(batch)
            for t in result.get("tracks") or []:
                if t:  # API can return None for unknown IDs
                    track_map[t["id"]] = t
            time.sleep(0.05)

        # --- audio features (max 50 per call; 403 is common — skip gracefully) ---
        audio_map: dict[str, dict] = {}
        try:
            for i in range(0, len(track_ids), 50):
                batch = track_ids[i : i + 50]
                feats = sp.audio_features(batch)
                if feats:
                    for f in feats:
                        if f:  # entries can be None when features are unavailable
                            audio_map[f["id"]] = f
                time.sleep(0.05)
        except spotipy.SpotifyException as e:
            # 403 / feature endpoint removed — proceed without audio features
            print(f"    [warn] audio_features unavailable: {e}")

        # --- artist genres: collect unique artist IDs from track objects ---
        artist_ids: list[str] = []
        seen_artists: set[str] = set()
        for t in track_map.values():
            for a in t.get("artists") or []:
                aid = a.get("id")
                if aid and aid not in seen_artists:
                    artist_ids.append(aid)
                    seen_artists.add(aid)

        # Fetch artist objects (max 50 per call) and build id → genres map
        artist_genres_map: dict[str, list[str]] = {}
        for i in range(0, len(artist_ids), 50):
            batch = artist_ids[i : i + 50]
            result = sp.artists(batch)
            for a in result.get("artists") or []:
                if a:
                    artist_genres_map[a["id"]] = a.get("genres") or []
            time.sleep(0.05)

    except spotipy.SpotifyException as e:
        # Any fetch failure — fall back to the unscored list
        print(f"    [warn] rec enrichment failed, using raw list: {e}")
        return new_recs[:n], True

    # ------------------------------------------------------------------
    # Steps 4-7: build profiles, score, filter, sort
    # ------------------------------------------------------------------
    scored: list[tuple[str, float]] = []
    rec_profiles: dict[str, dict] = {}

    for uri in new_recs:
        tid = uri.split(":")[-1]
        track_obj = track_map.get(tid)

        # Skip tracks for which we got no data (Spotify returned None)
        if not track_obj:
            continue

        # Build a minimal profile (no mining tags for recommendation candidates)
        prof = profile_mod.build(
            track_obj,
            artist_genres_map,
            audio_map,
            {},  # track_tags — empty for recs
        )
        rec_profiles[uri] = prof

        # Score against the target mood
        score = scorer.score_track(prof, mood_name)

        # -1.0 == hard reject; skip anything at or below the threshold
        if score > 0.15:
            scored.append((uri, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # ------------------------------------------------------------------
    # Step 7: cohesion filter — keep recs that fit the playlist cluster
    # ------------------------------------------------------------------
    if len(scored) >= 4:
        cohesion_pass = scorer.cohesion_filter(
            scored,
            rec_profiles,
            mood_name,
            threshold=cohesion_threshold,
        )
        if len(cohesion_pass) >= max(2, n // 3):
            scored = cohesion_pass

    # ------------------------------------------------------------------
    # Step 8: return top-n; flag fallback when we couldn't fill n
    # ------------------------------------------------------------------
    top = [uri for uri, _ in scored[:n]]
    fallback_mode = len(top) < n
    return top, fallback_mode
