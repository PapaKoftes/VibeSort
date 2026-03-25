"""
genre.py — Map Spotify's fine-grained genre strings to macro genre buckets.

Spotify has ~6000 genre tags. We reduce them to ~42 meaningful macro genres
using a keyword-rule approach (first match wins).
"""

import json
import os
import collections

_RULES: list[tuple[str, str]] | None = None

MACRO_GENRES = [
    "East Coast Rap",
    "West Coast Rap",
    "Southern Rap",
    "Houston Rap",
    "Midwest Rap",
    "UK Rap / Grime",
    "French Rap",
    "Phonk",
    "Brazilian Phonk",
    "Brazilian / Funk Carioca",
    "Latin / Reggaeton",
    "Mexican Regional",
    "R&B / Soul",
    "Dark R&B",
    "Electronic / House",
    "Electronic / Techno",
    "Electronic / Drum & Bass",
    "Electronic / Bass & Dubstep",
    "Electronic / Trance",
    "Electronic / Ambient",
    "Synthwave / Retrowave",
    "Lo-Fi",
    "Indie / Alternative",
    "Shoegaze / Dream Pop",
    "Post-Punk / Darkwave",
    "Emo / Post-Hardcore",
    "Punk / Hardcore",
    "Metal",
    "Rock",
    "Classic Rock",
    "Jazz / Blues",
    "Classical / Orchestral",
    "Pop",
    "K-Pop / J-Pop",
    "Hyperpop",
    "Country",
    "Folk / Americana",
    "Afrobeats / Amapiano",
    "Caribbean / Reggae",
    "World / Regional",
    "Ambient / Experimental",
    "Other",
]


def _load_rules() -> list[tuple[str, str]]:
    global _RULES
    if _RULES is not None:
        return _RULES
    rules_path = os.path.join(os.path.dirname(__file__), "..", "data", "macro_genres.json")
    with open(rules_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _RULES = [(pattern, macro) for pattern, macro in data["rules"]]
    return _RULES


def to_macro(genre: str) -> str:
    """Map a single Spotify genre string to its macro genre."""
    g = genre.lower()
    for pattern, macro in _load_rules():
        if pattern in g:
            return macro
    return "Other"


def track_macro_genres(track: dict, artist_genres: dict[str, list[str]]) -> list[str]:
    """Return deduplicated macro genres for a track based on its artists' genres."""
    seen: set[str] = set()
    result: list[str] = []
    for artist in track.get("artists", []):
        for genre in artist_genres.get(artist["id"], []):
            macro = to_macro(genre)
            if macro not in seen:
                seen.add(macro)
                result.append(macro)
    return result or ["Other"]


def library_genre_breakdown(
    tracks: list[dict],
    artist_genres: dict[str, list[str]],
) -> dict[str, list[str]]:
    """
    Returns {macro_genre: [track_uri, ...]} for the full library.
    A track can appear in multiple macro genres.
    """
    genre_map: dict[str, list[str]] = collections.defaultdict(list)
    seen_per_genre: dict[str, set] = collections.defaultdict(set)

    for track in tracks:
        uri = track.get("uri")
        if not uri:
            continue
        macros = track_macro_genres(track, artist_genres)
        for macro in macros:
            if uri not in seen_per_genre[macro]:
                seen_per_genre[macro].add(uri)
                genre_map[macro].append(uri)

    return dict(genre_map)


def era_breakdown(tracks: list[dict]) -> dict[str, list[str]]:
    """Group tracks by release decade."""
    ERA_LABELS = {
        1950: "The 50s", 1960: "The 60s", 1970: "The 70s",
        1980: "The 80s", 1990: "The 90s", 2000: "The 2000s",
        2010: "The 2010s", 2020: "The 2020s",
    }
    era_map: dict[str, list[str]] = collections.defaultdict(list)
    seen_per_era: dict[str, set] = collections.defaultdict(set)

    for track in tracks:
        uri = track.get("uri")
        if not uri:
            continue
        date = track.get("album", {}).get("release_date", "")
        if not date:
            continue
        try:
            year = int(date[:4])
        except (ValueError, IndexError):
            continue
        decade = (year // 10) * 10
        label = ERA_LABELS.get(decade, f"The {decade}s")
        if uri not in seen_per_era[label]:
            seen_per_era[label].add(uri)
            era_map[label].append(uri)

    return dict(era_map)


def artist_breakdown(tracks: list[dict], min_songs: int = 8) -> dict[str, list[str]]:
    """
    Returns {artist_name: [track_uri, ...]} for artists with >= min_songs
    in the library.
    """
    artist_map: dict[str, list[str]] = collections.defaultdict(list)
    seen: dict[str, set] = collections.defaultdict(set)

    for track in tracks:
        uri = track.get("uri")
        if not uri:
            continue
        for artist in track.get("artists", []):
            name = artist.get("name")
            if name and uri not in seen[name]:
                seen[name].add(uri)
                artist_map[name].append(uri)

    return {name: uris for name, uris in artist_map.items() if len(uris) >= min_songs}
