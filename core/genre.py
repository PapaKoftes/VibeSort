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


def _macro_fallback(g: str) -> str | None:
    """
    Last-resort heuristics when no macro_genres.json rule matched.
    Reduces everything landing in Other when Spotify uses uncommon genre strings.
    """
    if any(x in g for x in ("hip hop", "hip-hop", "hiphop", "rap", "trap", "drill", "grime", "boom bap", "cloud rap", "plugg")):
        return "Southern Rap"
    if any(x in g for x in ("edm", "house", "techno", "trance", "dubstep", "dnb", "drum and bass", "electronic", "electronica", "idm", "breakbeat", "garage", "jungle")):
        return "Electronic / House"
    if any(x in g for x in ("metal", "death", "black metal", "thrash", "doom", "core")):
        return "Metal"
    if any(x in g for x in ("punk", "hardcore", "screamo", "post-hardcore", "post hardcore")):
        return "Punk / Hardcore"
    if any(x in g for x in ("indie", "alternative", "alt-", "slowcore", "bedroom")):
        return "Indie / Alternative"
    if any(x in g for x in ("r&b", "rnb", "neo soul", "soul", "funk")):
        return "R&B / Soul"
    if any(x in g for x in ("pop", "singer", "vocal", "boy band", "girl group", "dance-pop")):
        return "Pop"
    if any(x in g for x in ("rock", "grunge", "britpop", "arena")):
        return "Rock"
    if any(x in g for x in ("jazz", "swing", "bebop", "fusion")):
        return "Jazz / Blues"
    if any(x in g for x in ("folk", "americana", "bluegrass", "celtic")):
        return "Folk / Americana"
    if any(x in g for x in ("country", "honky", "nashville")):
        return "Country"
    if any(x in g for x in ("latin", "reggaeton", "salsa", "bachata", "cumbia", "urbano")):
        return "Latin / Reggaeton"
    if any(x in g for x in ("afro", "amapiano", "afrobeats")):
        return "Afrobeats / Amapiano"
    if any(x in g for x in ("reggae", "dancehall", "ska", "dub")):
        return "Caribbean / Reggae"
    if any(x in g for x in ("ambient", "soundtrack", "score", "experimental")):
        return "Ambient / Experimental"
    if any(x in g for x in ("classical", "orchestral", "opera", "baroque", "chamber")):
        return "Classical / Orchestral"
    if any(x in g for x in ("k-pop", "kpop", "j-pop", "jpop", "anime", "city pop")):
        return "K-Pop / J-Pop"
    if any(x in g for x in ("world", "traditional", "regional", "african", "middle eastern", "indian", "asian")):
        return "World / Regional"
    return None


def to_macro(genre: str) -> str:
    """Map a single Spotify genre string to its macro genre."""
    g = genre.lower()
    for pattern, macro in _load_rules():
        if pattern in g:
            return macro
    fb = _macro_fallback(g)
    return fb if fb else "Other"


def track_macro_genres(track: dict, artist_genres: dict[str, list[str]]) -> list[str]:
    """Return deduplicated macro genres for a track based on its artists' genres."""
    seen: set[str] = set()
    result: list[str] = []
    for artist in track.get("artists", []):
        for genre in artist_genres.get(artist.get("id"), []):
            macro = to_macro(genre)
            if macro not in seen:
                seen.add(macro)
                result.append(macro)
    # Drop "Other" when real genres exist — it only means some raw genre strings
    # didn't match a rule, not that the track is genuinely unclassified.
    real = [g for g in result if g != "Other"]
    return real or ["Other"]


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
