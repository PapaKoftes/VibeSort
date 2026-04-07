"""
anchors.py — Curated high-quality anchor playlists per mood.

These Spotify editorial/popular playlists define each mood's sonic identity.
Used in playlist_mining to seed tag discovery before falling back to search.

Expansion rule: ≥100K followers, clear identity, no meme/novelty playlists.
Target: several editorial playlists per mood (~55+ moods). Keys are snake_case
slugs matching normalised pack titles (see get_anchor_ids).
"""

ANCHOR_PLAYLISTS: dict[str, list[str]] = {
    "late_night_drive": [
        "37i9dQZF1DX0XUsuxWHRQd",  # Night Drive
        "37i9dQZF1DX4E3UdUs7fUx",  # Late Night Driving
        "37i9dQZF1DXdQvOLqzNHSW",  # Midnight Drive
        "37i9dQZF1DX6GwdWRQMQpq",  # Drive & Chill
        "37i9dQZF1DWXti3N73pG0S",  # Cruise Control
    ],
    "hollow": [
        "37i9dQZF1DX7qK8ma5wgG1",  # Sad Songs
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
        "37i9dQZF1DX4sWSpwq3LiO",  # Life Sucks
        "37i9dQZF1DXa71dSCed4Q",   # Breaking Up
        "37i9dQZF1DX59NCihbCKCr",  # Melancholia
    ],
    "heartbreak": [
        "37i9dQZF1DXa71dSCed4Q",   # Breaking Up
        "37i9dQZF1DX7qK8ma5wgG1",  # Sad Songs
        "37i9dQZF1DX8tZsk68tuDw",  # Dark Mode
    ],
    "overthinking": [
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
        "37i9dQZF1DX4sWSpwq3LiO",  # Life Sucks
        "37i9dQZF1DXfA0A6hFNlpq",  # Mind Trip
    ],
    "adrenaline": [
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
        "37i9dQZF1DX8tZsk68tuDw",  # Power Workout
        "37i9dQZF1DXdxcBWuJkRyd",  # Workout Twerkout
        "37i9dQZF1DX70RN3TfWWJh",  # Pumped Pop
        "37i9dQZF1DX2RxBh64BHjQ",  # Intense Workout
    ],
    "phonk_season": [
        "37i9dQZF1DX6VdMW310YC7",  # Phonk
        "37i9dQZF1DX1tyCD9QhIWF",  # Phonk Drive
        "37i9dQZF1DXdSjFyQHBSlN",  # Dark Phonk
        "37i9dQZF1DX3NeZpwKRCM0",  # Brazilian Phonk
    ],
    "deep_focus": [
        "37i9dQZF1DX8Uebhn9wzrS",  # Deep Focus
        "37i9dQZF1DWZeKCadgRdKQ",  # Music for Concentration
        "37i9dQZF1DX4sWSpwq3LiO",  # Focus Flow
        "37i9dQZF1DXaXBclqnQs8B",  # Study Vibes
    ],
    "nostalgia": [
        "37i9dQZF1DX4UtSsGT1Sbe",  # Throwback Jams
        "37i9dQZF1DX4o1oenSJRJd",  # Throwbacks
        "37i9dQZF1DXa7fFoRjdWKQ",  # Old School
        "37i9dQZF1DX3LyoiQlJfFJ",  # All Out 2000s
    ],
    "chill_out": [
        "37i9dQZF1DX4WYpdgoIcn6",  # Chill Hits
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DXa7fFoRjdWKQ",  # Lounge
        "37i9dQZF1DWYcDQ1hSjOpY",  # Coffee & Chill
    ],
    "summer_high": [
        "37i9dQZF1DX2MyUCsl25eb",  # Summer Hits
        "37i9dQZF1DXdNa1MWk3DDE",  # Hot Hits
        "37i9dQZF1DX4dyzvuaRJ0n",  # Beach Vibes
        "37i9dQZF1DX70RN3TfWWJh",  # Happy Hits
    ],
    "gospel_fire": [
        "37i9dQZF1DWUileP28cBmK",  # Gospel Hits
        "37i9dQZF1DX7K31NsF3Yj2",  # Contemporary Christian
        "37i9dQZF1DXcJMzFRnHPgS",  # Praise & Worship
    ],
    "late_night_rb": [
        "37i9dQZF1DX4SBhb3fqCJd",  # Late Night R&B
        "37i9dQZF1DWXRqgorJj26U",  # R&B Party
        "37i9dQZF1DX2A29LI7xHn1",  # Slow Jams
    ],
    "villain_arc": [
        "37i9dQZF1DX6VdMW310YC7",  # Phonk
        "37i9dQZF1DX8tZsk68tuDw",  # Dark Mode
        "37i9dQZF1DXdSjFyQHBSlN",  # Dark Phonk
    ],
    "lo_fi_flow": [
        "37i9dQZF1DWWQRwui0ExPn",  # lofi beats
        "37i9dQZF1DX3PFzdbtxmM0",  # lofi hip-hop
        "37i9dQZF1DX8Uebhn9wzrS",  # Deep Focus
        "37i9dQZF1DWZeKCadgRdKQ",  # Music for Concentration
    ],
    "rainy_window": [
        "37i9dQZF1DXcBW6oWax0E6",  # Rainy Day
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
        "37i9dQZF1DWYcDQ1hSjOpY",  # Coffee & Chill
    ],
    "latin_heat": [
        "37i9dQZF1DX10zQHsJ1Wmv",  # Viva Latino
        "37i9dQZF1DWXcCc4c9Cekk",  # Baila Reggaeton
        "37i9dQZF1DX4aWZk7QKNKf",  # Latin Pop Rising
        "37i9dQZF1DWYfBCJlM52fy",  # ¡Viva Latino!
    ],
    "metal_storm": [
        "37i9dQZF1DX2FrSudPyD8X",  # Metal Ballads
        "37i9dQZF1DWTvN65O0eYW9",  # Metal
        "37i9dQZF1DX9qNs32fqvrm",  # Metalcore
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
    ],
    "classical_calm": [
        "37i9dQZF1DWWEJlAGA9gs0",  # Classical Essentials
        "37i9dQZF1DWV7EzJMK2tUI",  # Peaceful Piano
        "37i9dQZF1DX3Ogo9pFvBkY",  # Classical New Releases
    ],
    "rage_lift": [
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
        "37i9dQZF1DX8tZsk68tuDw",  # Power Workout
        "37i9dQZF1DWSZ5nqV5Mn4V",  # Trap Workout
        "37i9dQZF1DX2FrSudPyD8X",  # Metal Ballads
    ],
    "healing_kind": [
        "37i9dQZF1DX3XxgXMaStLY",  # Peaceful Piano
        "37i9dQZF1DX1S7wt5GBFQp",  # Mood Booster
        "37i9dQZF1DX4SBhb3fqCJd",  # Late Night R&B
        "37i9dQZF1DX2A29LI7xHn1",  # Slow Jams
    ],
    "disco_lights": [
        "37i9dQZF1DX18BZjlWsEjh",  # Disco Forever
        "37i9dQZF1DX4UtSsGT1Sbe",  # Throwback Jams
        "37i9dQZF1DX4WYpdgoIcn6",  # Chill Hits
    ],
    "amapiano_sunset": [
        "37i9dQZF1DXdL65KMdj7tq",  # AmaPiano Grooves
        "37i9dQZF1DXbS0bJbhiM9e",  # African Heat
        "37i9dQZF1DX4m0VcJj1XyF",  # Afro Hits
    ],
    "punk_sprint": [
        "37i9dQZF1DWWJCYbMTDqlu",  # Punk Rock
        "37i9dQZF1DX717NAqvdPUr",  # Pop Punk's Not Dead
        "37i9dQZF1DX6J3N9HOIJO9",  # Skatepark Punks
    ],
    "dream_pop_haze": [
        "37i9dQZF1DX6ukDaGB3jkG",  # Dreampop
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
    ],
    "warehouse_techno": [
        "37i9dQZF1DWTvqKnkeVCMm",  # Techno Bunker
        "37i9dQZF1DX2Dw5au9rblO",  # HYPERTECHNO
        "37i9dQZF1DX1rjWh5SEJpr",  # Peak Time Techno
    ],
    "anime_ost_energy": [
        "37i9dQZF1DWX84Vx0Hwh75",  # Anime Rewind
        "37i9dQZF1DX6GwdWRQMQpq",  # Drive & Chill
        "37i9dQZF1DX1s9knjP51Oa",  # Anime on Replay
    ],
    "chillhop_cafe": [
        "37i9dQZF1DWSrsfFwAFrHV",  # Jazz Vibes
        "37i9dQZF1DWYcDQ1hSjOpY",  # Coffee & Chill
        "37i9dQZF1DWWQRwui0ExPn",  # lofi beats
    ],
    "meditation_bath": [
        "37i9dQZF1DWXCDWiqI5oXN",  # Meditation
        "37i9dQZF1DX8Uebhn9wzrS",  # Deep Focus
        "37i9dQZF1DWV7EzJMK2tUI",  # Peaceful Piano
    ],
    "vaporwave": [
        "37i9dQZF1DX4wtaErmWyKm",  # aesthetic / chillwave-adjacent editorial rotation
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DX4o1oenSJRJd",  # Throwbacks
    ],
    "j_pop": [
        "37i9dQZF1DX1s9knjP51Oa",  # Anime on Replay
        "37i9dQZF1DWX84Vx0Hwh75",  # Anime Rewind
        "37i9dQZF1DX70RN3TfWWJh",  # Happy Hits
    ],
    "j_metal": [
        "37i9dQZF1DX2FrSudPyD8X",  # Metal Ballads
        "37i9dQZF1DWTvN65O0eYW9",  # Metal
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
    ],
    "anime_openings": [
        "37i9dQZF1DWX84Vx0Hwh75",  # Anime Rewind
        "37i9dQZF1DX1s9knjP51Oa",  # Anime on Replay
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
    ],
    "anime_endings": [
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
        "37i9dQZF1DX1s9knjP51Oa",  # Anime on Replay
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
    ],
    "songs_about_goodbye": [
        "37i9dQZF1DX7qK8ma5wgG1",  # Sad Songs
        "37i9dQZF1DXa71dSCed4Q",  # Breaking Up
        "37i9dQZF1DX59NCihbCKCr",  # Melancholia
    ],
    "songs_about_home": [
        "37i9dQZF1DX4sWSpwq3LiO",  # Life Sucks / reflective
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DX4UtSsGT1Sbe",  # Throwback Jams
    ],
    "same_vibe_different_genre": [
        "37i9dQZF1DX70RN3TfWWJh",  # Happy Hits
        "37i9dQZF1DX4WYpdgoIcn6",  # Chill Hits
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
    ],
    "3_am_unsent_texts": [
        "37i9dQZF1DX7qK8ma5wgG1",  # Sad Songs
        "37i9dQZF1DXa71dSCed4Q",  # Breaking Up
        "37i9dQZF1DX59NCihbCKCr",  # Melancholia
    ],
    "anti_hero_receipts": [
        "37i9dQZF1DX8tZsk68tuDw",  # Dark Mode
        "37i9dQZF1DX6VdMW310YC7",  # Phonk
        "37i9dQZF1DXdSjFyQHBSlN",  # Dark Phonk
    ],
    "money_talks": [
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
        "37i9dQZF1DWSZ5nqV5Mn4V",  # Trap Workout
        "37i9dQZF1DX70RN3TfWWJh",  # Pumped Pop
    ],
    "runaway_highways": [
        "37i9dQZF1DX6GwdWRQMQpq",  # Drive & Chill
        "37i9dQZF1DX0XUsuxWHRQd",  # Night Drive
        "37i9dQZF1DX4UtSsGT1Sbe",  # Throwback Jams
    ],
    "drill_confessions": [
        "37i9dQZF1DX2yvHY24Vo0S",  # UK Rap
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
        "37i9dQZF1DWSZ5nqV5Mn4V",  # Trap Workout
    ],
    "shoegaze_breakups": [
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
        "37i9dQZF1DX59NCihbCKCr",  # Melancholia
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
    ],
    "queer_dance_confetti": [
        "37i9dQZF1DX70RN3TfWWJh",  # Happy Hits
        "37i9dQZF1DX4WYpdgoIcn6",  # Chill Hits
        "37i9dQZF1DX2RxBh64BHjQ",  # Intense Workout / party-adjacent
    ],
    "metal_testimony": [
        "37i9dQZF1DX2FrSudPyD8X",  # Metal Ballads
        "37i9dQZF1DWTvN65O0eYW9",  # Metal
        "37i9dQZF1DXcJMzFRnHPgS",  # Praise & Worship
    ],
    "bedroom_pop_diary": [
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DX4sWSpwq3LiO",  # Life Sucks
    ],
    "baroque_pop_melodrama": [
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
        "37i9dQZF1DX59NCihbCKCr",  # Melancholia
        "37i9dQZF1DX7qK8ma5wgG1",  # Sad Songs
    ],
    "sea_shanty_singalong": [
        "37i9dQZF1DX4sWSpwq3LiO",  # Life Sucks / broad folk-adjacent
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DWYcDQ1hSjOpY",  # Coffee & Chill
    ],
    "brass_&_drumline_energy": [
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
        "37i9dQZF1DX8tZsk68tuDw",  # Power Workout
        "37i9dQZF1DX70RN3TfWWJh",  # Pumped Pop
    ],
    "symphonic_metal_epics": [
        "37i9dQZF1DWTvN65O0eYW9",  # Metal
        "37i9dQZF1DX2FrSudPyD8X",  # Metal Ballads
        "37i9dQZF1DX9qNs32fqvrm",  # Metalcore
    ],
    "minimal_techno_tunnel": [
        "37i9dQZF1DX8Uebhn9wzrS",  # Deep Focus
        "37i9dQZF1DWZeKCadgRdKQ",  # Music for Concentration
        "37i9dQZF1DXaXBclqnQs8B",  # Study Vibes
    ],
    "cloud_rap_haze": [
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DWWQRwui0ExPn",  # lofi beats
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
    ],
    "latin_ballroom_heat": [
        "37i9dQZF1DX10zQHsJ1Wmv",  # Viva Latino
        "37i9dQZF1DWXcCc4c9Cekk",  # Baila Reggaeton
        "37i9dQZF1DX4aWZk7QKNKf",  # Latin Pop Rising
    ],
    "afro_fusion_golden_hour": [
        "37i9dQZF1DXdL65KMdj7tq",  # AmaPiano Grooves
        "37i9dQZF1DXbS0bJbhiM9e",  # African Heat
        "37i9dQZF1DX4m0VcJj1XyF",  # Afro Hits
    ],
    "hyperpop_emotional_crash": [
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
        "37i9dQZF1DX59NCihbCKCr",  # Melancholia
        "37i9dQZF1DX70RN3TfWWJh",  # Happy Hits
    ],
    "industrial_gothic_floor": [
        "37i9dQZF1DX8tZsk68tuDw",  # Dark Mode
        "37i9dQZF1DX6VdMW310YC7",  # Phonk
        "37i9dQZF1DXdSjFyQHBSlN",  # Dark Phonk
    ],
    "country_story_hour": [
        "37i9dQZF1DX4UtSsGT1Sbe",  # Throwback Jams
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
    ],
    "kawaii_metal_sparkle": [
        "37i9dQZF1DWTvN65O0eYW9",  # Metal
        "37i9dQZF1DX76Wlfdnj7AP",  # Beast Mode
        "37i9dQZF1DX1s9knjP51Oa",  # Anime on Replay
    ],
    "pluggnb_heartache": [
        "37i9dQZF1DX889U0CL85jj",  # Chill Vibes
        "37i9dQZF1DX3YSRoSdA634",  # Sad Indie
        "37i9dQZF1DWWQRwui0ExPn",  # lofi beats
    ],
}

# Normalise mood names → anchor keys
_MOOD_KEY_MAP: dict[str, str] = {
    k.lower().replace(" ", "_").replace("-", "_"): k
    for k in ANCHOR_PLAYLISTS
}


def _normalise_mood_key(mood_name: str) -> str:
    s = mood_name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def get_anchor_ids(mood_name: str) -> list[str]:
    """Return curated anchor playlist IDs for a mood. Empty list if none defined."""
    key = _normalise_mood_key(mood_name)
    canonical = _MOOD_KEY_MAP.get(key, key)
    return list(ANCHOR_PLAYLISTS.get(canonical, []))


# ── Track-level anchors (M1.4) ────────────────────────────────────────────────
# data/mood_anchors.json: {mood_name: [{artist, title}, ...]}
# Generated by scripts/generate_anchors.py + human review.
# Matching gives anchor_<moodname>: 1.0 — the highest-confidence mood signal.

import json as _json
import os as _os
import re as _re

_ANCHORS_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "data", "mood_anchors.json",
)

# Strip "feat." and parenthetical suffixes for more robust title matching.
_FEAT_PATTERN = _re.compile(
    r"\s*[\(\[\{].*?[\)\]\}]|\s+feat\..*$|\s+ft\..*$",
    _re.IGNORECASE,
)


def _clean_title(title: str) -> str:
    return _FEAT_PATTERN.sub("", title).strip().lower()


def load_mood_anchors() -> dict:
    """
    Load data/mood_anchors.json.

    Returns:
        {mood_name: [{"artist": str, "title": str}, ...]}
    Returns empty dict if file does not exist (pre-human-review state).
    """
    try:
        with open(_ANCHORS_PATH, "r", encoding="utf-8") as f:
            data = _json.load(f)
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, _json.JSONDecodeError):
        pass
    return {}


def build_anchor_lookup(mood_anchors: dict) -> dict:
    """
    Build a fast lookup from mood_anchors dict.

    Returns:
        {(artist_lower, clean_title_lower): [mood_name, ...]}
    A single track may appear as anchor for multiple moods — all are returned.
    """
    lookup: dict = {}
    for mood_name, tracks in mood_anchors.items():
        for entry in tracks:
            artist = (entry.get("artist") or "").lower().strip()
            title  = _clean_title(entry.get("title") or "")
            if artist and title:
                lookup.setdefault((artist, title), []).append(mood_name)
    return lookup


def apply_anchor_tags(
    all_tracks: list,
    track_tags: dict,
    anchor_lookup: dict = None,
) -> int:
    """
    Inject anchor_<moodname>: 1.0 into track_tags for any library track that
    matches a known mood anchor (artist + title, case-insensitive, feat.-stripped).

    Args:
        all_tracks:    Full library track list (Spotify track dicts).
        track_tags:    {uri: {tag: weight}} — modified in place.
        anchor_lookup: Pre-built lookup from build_anchor_lookup(). If None,
                       loads and builds from mood_anchors.json automatically.

    Returns:
        Number of (track, mood) anchor matches applied.
    """
    if anchor_lookup is None:
        anchors = load_mood_anchors()
        if not anchors:
            return 0
        anchor_lookup = build_anchor_lookup(anchors)

    if not anchor_lookup:
        return 0

    matched = 0
    for track in all_tracks:
        uri = track.get("uri", "")
        if not uri:
            continue
        artists = track.get("artists") or []
        title   = _clean_title(track.get("name") or "")
        for artist_obj in artists:
            artist = (artist_obj.get("name") or "").lower().strip()
            mood_names = anchor_lookup.get((artist, title))
            if mood_names:
                if uri not in track_tags:
                    track_tags[uri] = {}
                for mood_name in mood_names:
                    tag_key = "anchor_" + _normalise_mood_key(mood_name)
                    track_tags[uri][tag_key] = 1.0
                    matched += 1
                break  # primary artist match found — stop iterating artists

    return matched
