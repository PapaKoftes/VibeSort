"""
playlist_mining.py — Extract human meaning from Spotify playlist names.

This is the core signal layer. The idea:
  - Search Spotify for public playlists matching mood/vibe keywords
  - Check which of those playlists contain tracks from the user's library
  - Extract semantic tags from playlist names (e.g. "late night drive" → night, drive)
  - Weight tags by playlist follower count (more followers = stronger signal)
  - Build a per-track tag profile: {uri: {tag: weight}}

This reconstructs how humans ACTUALLY categorize music — not by audio physics,
but by the vibes and contexts people associate with songs.

Results are cached to outputs/.mining_cache.json (refreshed every 7 days).
"""

import re
import json
import os
import math
import time
import collections
import spotipy

CACHE_PATH = os.path.join("outputs", ".mining_cache.json")
CACHE_TTL_DAYS = 7

# Stopwords to remove when extracting tags from playlist names
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "be", "been", "my",
    "your", "our", "their", "its", "this", "that", "these", "those", "it",
    "playlist", "music", "songs", "tracks", "mix", "vibes", "hits", "vol",
    "best", "top", "new", "i", "you", "we", "they", "he", "she",
}

# Common multi-word phrases to keep intact (before single-word extraction)
COMPOUND_TAGS = [
    "late night", "night drive", "late night drive", "dark phonk",
    "gym rage", "deep focus", "chill vibes", "sad songs", "feel good",
    "good vibes", "golden hour", "after hours", "lo fi", "lo-fi",
    "study music", "work out", "warm up", "slow burn", "broken heart",
    "overthinking", "night time", "drive home", "summer vibes",
    "dark energy", "villain arc", "hype up", "turn up", "come down",
]


# ── Tag extraction ─────────────────────────────────────────────────────────────

def extract_tags(text: str) -> list[str]:
    """
    Extract meaningful tags from a playlist name or description.
    Returns a list of normalized tag strings.
    """
    text_lower = text.lower()
    tags: list[str] = []

    # First extract compound phrases
    for phrase in COMPOUND_TAGS:
        if phrase in text_lower:
            tags.append(phrase.replace(" ", "_"))

    # Then extract single words
    words = re.findall(r"[a-z]+", text_lower)
    for word in words:
        if word not in STOPWORDS and len(word) > 2:
            tags.append(word)

    return list(dict.fromkeys(tags))  # deduplicate preserving order


# ── Playlist fetching ─────────────────────────────────────────────────────────

def _search_playlists(sp: spotipy.Spotify, query: str, limit: int = 5) -> list[dict]:
    """Search for public playlists matching a query."""
    try:
        result = sp.search(q=query, type="playlist", limit=limit)
        return result.get("playlists", {}).get("items", [])
    except Exception:
        return []


def _playlist_track_uris(sp: spotipy.Spotify, playlist_id: str, max_tracks: int = 100) -> list[str]:
    """Fetch track URIs from a playlist (first page only for speed)."""
    try:
        result = sp.playlist_items(
            playlist_id,
            limit=min(max_tracks, 100),
            additional_types=["track"],
        )
        uris = []
        for item in result.get("items", []):
            t = item.get("track")
            if t and t.get("uri") and t["uri"].startswith("spotify:track:"):
                uris.append(t["uri"])
        return uris
    except Exception:
        return []


# ── Cache ─────────────────────────────────────────────────────────────────────

def _load_cache() -> dict | None:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        import datetime
        ts = data.get("_timestamp", "")
        if ts:
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(ts)).days
            if age > CACHE_TTL_DAYS:
                return None
        return data
    except Exception:
        return None


def _save_cache(data: dict) -> None:
    import datetime
    os.makedirs("outputs", exist_ok=True)
    data["_timestamp"] = datetime.datetime.now().isoformat()
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ── Core mining ───────────────────────────────────────────────────────────────

def mine(
    sp: spotipy.Spotify,
    user_uris: set[str],
    mood_packs: dict,
    playlists_per_seed: int = 4,
    max_tracks_per_playlist: int = 100,
    force_refresh: bool = False,
) -> dict:
    """
    Mine public Spotify playlists for track context.

    Returns:
      {
        "track_tags":    {uri: {tag: weight}},
        "track_context": {uri: [{playlist_name, followers, mood, tags}]},
        "tag_index":     {tag: [uri, ...]},
      }
    """
    if not force_refresh:
        cached = _load_cache()
        if cached:
            print("  Playlist mining       loaded from cache")
            return cached

    print("  Playlist mining       scanning public playlists...")

    track_context: dict[str, list[dict]] = collections.defaultdict(list)
    searched_playlists: set[str] = set()  # avoid fetching same playlist twice

    # Collect all seed phrases from packs
    all_seeds: list[tuple[str, str]] = []  # (mood_name, phrase)
    for mood_name, pack in mood_packs.items():
        for phrase in pack.get("seed_phrases", [])[:3]:  # top 3 per mood
            all_seeds.append((mood_name, phrase))

    total = len(all_seeds)
    for idx, (mood_name, phrase) in enumerate(all_seeds):
        print(f"\r  Playlist mining       {idx+1}/{total} — {phrase[:30]:<30}", end="", flush=True)

        playlists = _search_playlists(sp, phrase, limit=playlists_per_seed)
        time.sleep(0.1)

        for pl in playlists:
            if not pl:
                continue
            pid = pl.get("id")
            if not pid or pid in searched_playlists:
                continue
            searched_playlists.add(pid)

            pl_name = pl.get("name", "")
            followers = (pl.get("followers") or {}).get("total", 0)

            track_uris = _playlist_track_uris(sp, pid, max_tracks_per_playlist)
            time.sleep(0.08)

            tags = extract_tags(pl_name)

            for uri in track_uris:
                if uri in user_uris:
                    track_context[uri].append({
                        "playlist":  pl_name,
                        "followers": followers,
                        "mood":      mood_name,
                        "tags":      tags,
                    })

    print(f"\r  Playlist mining       done — {len(searched_playlists)} playlists, "
          f"{len(track_context)} matched tracks          ")

    # Build weighted tag scores per track
    track_tags: dict[str, dict[str, float]] = {}
    tag_index: dict[str, list[str]] = collections.defaultdict(list)

    for uri, contexts in track_context.items():
        tag_weights: dict[str, float] = collections.defaultdict(float)

        for ctx in contexts:
            # Weight = log(followers + 1) normalized, capped at 1.0
            follower_weight = min(math.log1p(ctx["followers"]) / 14.0, 1.0)
            for tag in ctx["tags"]:
                tag_weights[tag] += follower_weight

        # Normalize to [0, 1]
        if tag_weights:
            max_w = max(tag_weights.values())
            track_tags[uri] = {t: round(w / max_w, 4) for t, w in tag_weights.items()}
        else:
            track_tags[uri] = {}

        for tag in track_tags[uri]:
            if uri not in tag_index[tag]:
                tag_index[tag].append(uri)

    result = {
        "track_tags":    track_tags,
        "track_context": {k: v for k, v in track_context.items()},
        "tag_index":     dict(tag_index),
    }
    _save_cache(result)
    return result
