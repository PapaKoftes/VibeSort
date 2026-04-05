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
