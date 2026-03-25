"""
namer.py — Three-engine playlist naming system.

Top-down:    User picks a preset vibe → uses preset name
Bottom-up:   Looks at actual genres/tags in the playlist → names what's there
Middle-out:  Clusters meet taxonomy → use taxonomy where strong match,
             hybrid where partial, bottom-up where no match
"""

import collections
from typing import Optional


# ── Audio vector index constants ─────────────────────────────────────────────
# audio_vector = [energy, valence, danceability, tempo_norm, acousticness, instrumentalness]
_IDX_ENERGY        = 0
_IDX_VALENCE       = 1
_IDX_DANCE         = 2
_IDX_TEMPO         = 3
_IDX_ACOUSTIC      = 4
_IDX_INSTRUMENTAL  = 5


# ── Adjective tables for hybrid names ─────────────────────────────────────────
_ENERGY_ADJECTIVES = {
    "high":   ["Heavy", "Hard", "Loud", "Intense"],
    "mid":    ["Deep", "Dark", "Cold", "Sharp"],
    "low":    ["Slow", "Soft", "Quiet", "Mellow"],
}

_VALENCE_ADJECTIVES = {
    "positive": ["Warm", "Golden", "Bright", "Light"],
    "mid":      ["Grey", "Open", "Still"],
    "negative": ["Dark", "Hollow", "Cold", "Bleak"],
}


def energy_descriptor(audio_mean: list[float]) -> str:
    """
    Map an audio mean vector to a plain-English energy description.

    Args:
        audio_mean: 6-element list [energy, valence, danceability,
                    tempo_norm, acousticness, instrumentalness]

    Returns:
        A concise descriptor string, e.g. "High Energy", "Chill", "Dark & Heavy"
    """
    if not audio_mean or len(audio_mean) < 6:
        return "Mixed"

    energy       = audio_mean[_IDX_ENERGY]
    valence      = audio_mean[_IDX_VALENCE]
    acoustic     = audio_mean[_IDX_ACOUSTIC]
    instrumental = audio_mean[_IDX_INSTRUMENTAL]
    dance        = audio_mean[_IDX_DANCE]

    # Ordered checks — first match wins
    if energy >= 0.85 and valence <= 0.35:
        return "Dark & Heavy"
    if energy >= 0.85:
        return "High Energy"
    if energy >= 0.70 and dance >= 0.70:
        return "Hard & Fast"
    if energy >= 0.70 and valence <= 0.30:
        return "Dark"
    if energy >= 0.65:
        return "Intense"
    if valence <= 0.20 and energy <= 0.35:
        return "Melancholic"
    if valence <= 0.30:
        return "Dark"
    if acoustic >= 0.70:
        return "Soft & Acoustic"
    if instrumental >= 0.55:
        return "Atmospheric"
    if energy <= 0.35 and valence >= 0.55:
        return "Chill"
    if energy <= 0.35:
        return "Low Energy"
    if valence >= 0.75 and energy >= 0.55:
        return "Euphoric"
    if valence >= 0.65:
        return "Melodic"
    return "Mixed"


def genre_summary(track_profiles: list[dict]) -> dict:
    """
    Compute macro genre breakdown for a list of track profiles.

    Returns:
        dict of {macro_genre: {"count": int, "percentage": float}}
        sorted by count descending.
    """
    counts: dict[str, int] = collections.Counter()
    total = 0

    for profile in track_profiles:
        for macro in profile.get("macro_genres", ["Other"]):
            if macro != "Other":
                counts[macro] += 1
                total += 1

    if total == 0:
        return {"Other": {"count": len(track_profiles), "percentage": 1.0}}

    result = {}
    for genre, count in sorted(counts.items(), key=lambda x: -x[1]):
        result[genre] = {
            "count":      count,
            "percentage": round(count / total, 3),
        }
    return result


def _dominant_genres(track_profiles: list[dict], top_n: int = 2) -> list[str]:
    """Return the top-N macro genres by track count."""
    summary = genre_summary(track_profiles)
    return list(summary.keys())[:top_n]


def _audio_mean_from_profiles(track_profiles: list[dict]) -> list[float]:
    """Compute the mean audio vector across a list of track profiles."""
    vectors = [p.get("audio_vector", [0.5] * 6) for p in track_profiles if p.get("audio_vector")]
    if not vectors:
        return [0.5] * 6
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(6)]


def _unique_artists(track_profiles: list[dict]) -> list[str]:
    """Collect all unique artist names across the profile list."""
    seen: set[str] = set()
    artists: list[str] = []
    for profile in track_profiles:
        for name in profile.get("artists", []):
            if name and name not in seen:
                seen.add(name)
                artists.append(name)
    return artists


def bottom_up_name(track_profiles: list[dict]) -> tuple[str, str]:
    """
    Generate a playlist name and description purely from the track data.

    - Finds dominant 1-2 macro genres
    - Generates a clean genre-based name
    - Builds a factual description with energy info
    - Never uses artist names (unless all tracks share one artist)
    - Never generates abstract nouns alone

    Args:
        track_profiles: list of track profile dicts

    Returns:
        (name, description) tuple
    """
    if not track_profiles:
        return ("Playlist", "Empty playlist.")

    summary = genre_summary(track_profiles)
    top_genres = list(summary.keys())[:2]
    track_count = len(track_profiles)
    audio_mean = _audio_mean_from_profiles(track_profiles)
    descriptor = energy_descriptor(audio_mean)

    # Build name
    if not top_genres:
        name = "Mixed"
    elif len(top_genres) == 1:
        name = top_genres[0]
    else:
        top_pct = summary[top_genres[0]]["percentage"]
        if top_pct >= 0.70:
            name = top_genres[0]
        else:
            # Blend the top two
            g1, g2 = top_genres[0], top_genres[1]
            # Shorten long genre names for the combined form
            short1 = _shorten_genre(g1)
            short2 = _shorten_genre(g2)
            name = f"{short1} / {short2}"

    # Build description
    genre_parts = []
    for g, info in list(summary.items())[:3]:
        pct = int(info["percentage"] * 100)
        genre_parts.append(f"{g} ({pct}%)")

    genre_str = ", ".join(genre_parts) if genre_parts else "Various genres"
    description = f"{track_count} tracks — {genre_str}. {descriptor}."

    return (name, description)


def top_down_name(mood_name: str, track_profiles: list[dict]) -> tuple[str, str]:
    """
    Generate a playlist name and description using a preset mood name.

    - Uses the mood preset name directly as the playlist name
    - Enriches the description with actual genre breakdown

    Args:
        mood_name:      The preset mood name (e.g. "Late Night Drive")
        track_profiles: list of track profile dicts

    Returns:
        (name, description) tuple
    """
    from core.mood_graph import get_mood

    pack = get_mood(mood_name) or {}
    pack_desc = pack.get("description", mood_name)

    track_count = len(track_profiles)
    audio_mean = _audio_mean_from_profiles(track_profiles)
    descriptor = energy_descriptor(audio_mean)

    summary = genre_summary(track_profiles)
    top_genres = list(summary.keys())[:2]
    genre_str = " / ".join(_shorten_genre(g) for g in top_genres) if top_genres else "Various"

    description = (
        f"{pack_desc}. "
        f"{track_count} tracks — {genre_str}. "
        f"{descriptor}."
    )
    return (mood_name, description)


def middle_out_name(
    track_profiles: list[dict],
    mood_name: Optional[str] = None,
) -> tuple[str, str]:
    """
    Hybrid naming: uses the strongest signal available.

    Decision logic:
      1. If >60% tracks share one macro genre → use genre name (bottom-up dominant)
      2. If mood_name provided AND audio profile closely matches mood target → use mood name
      3. Otherwise → hybrid: "{energy_descriptor} {top_genre_short}" e.g. "Dark Latin Phonk"

    Args:
        track_profiles: list of track profile dicts
        mood_name:      optional preset mood name

    Returns:
        (name, description) tuple
    """
    if not track_profiles:
        return ("Playlist", "Empty playlist.")

    summary = genre_summary(track_profiles)
    top_genres = list(summary.keys())
    track_count = len(track_profiles)
    audio_mean = _audio_mean_from_profiles(track_profiles)
    descriptor = energy_descriptor(audio_mean)

    # Decision 1: Strong single-genre dominance
    if top_genres and summary[top_genres[0]]["percentage"] >= 0.60:
        dominant = top_genres[0]
        pct = int(summary[dominant]["percentage"] * 100)
        second = top_genres[1] if len(top_genres) > 1 else None
        second_str = f", {_shorten_genre(second)}" if second else ""
        desc = (
            f"{track_count} tracks — {dominant}{second_str}. "
            f"{descriptor}."
        )
        return (dominant, desc)

    # Decision 2: Mood match
    if mood_name:
        mood_match = _mood_audio_match(audio_mean, mood_name)
        if mood_match >= 0.72:
            return top_down_name(mood_name, track_profiles)

    # Decision 3: Hybrid name
    if top_genres:
        short_genre = _shorten_genre(top_genres[0])
        hybrid_name = f"{descriptor} {short_genre}".strip()
    else:
        hybrid_name = f"{descriptor} Mix"

    genre_parts = [_shorten_genre(g) for g in top_genres[:3]]
    genre_str = " / ".join(genre_parts) if genre_parts else "Various"
    description = f"{track_count} tracks — {genre_str}. {descriptor}."

    return (hybrid_name, description)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _shorten_genre(genre: str) -> str:
    """Shorten long genre names for use in hybrid names."""
    SHORT_MAP = {
        "East Coast Rap":             "East Coast",
        "West Coast Rap":             "West Coast",
        "Southern Rap":               "Southern Rap",
        "Houston Rap":                "Houston",
        "Midwest Rap":                "Midwest Rap",
        "UK Rap / Grime":             "UK Rap",
        "French Rap":                 "French Rap",
        "Brazilian Phonk":            "Brazilian Phonk",
        "Brazilian / Funk Carioca":   "Funk Carioca",
        "Latin / Reggaeton":          "Latin",
        "Mexican Regional":           "Regional",
        "R&B / Soul":                 "R&B",
        "Dark R&B":                   "Dark R&B",
        "Electronic / House":         "House",
        "Electronic / Techno":        "Techno",
        "Electronic / Drum & Bass":   "DnB",
        "Electronic / Bass & Dubstep":"Bass",
        "Electronic / Trance":        "Trance",
        "Electronic / Ambient":       "Ambient",
        "Synthwave / Retrowave":      "Synthwave",
        "Indie / Alternative":        "Indie",
        "Shoegaze / Dream Pop":       "Shoegaze",
        "Post-Punk / Darkwave":       "Darkwave",
        "Emo / Post-Hardcore":        "Emo",
        "Punk / Hardcore":            "Hardcore",
        "Classical / Orchestral":     "Classical",
        "K-Pop / J-Pop":              "K-Pop",
        "Folk / Americana":           "Folk",
        "Afrobeats / Amapiano":       "Afrobeats",
        "Caribbean / Reggae":         "Reggae",
        "World / Regional":           "World",
        "Ambient / Experimental":     "Experimental",
        "Classic Rock":               "Classic Rock",
    }
    return SHORT_MAP.get(genre, genre)


def _mood_audio_match(audio_mean: list[float], mood_name: str) -> float:
    """
    Compute cosine similarity between actual audio mean and mood's target vector.
    Returns float in [0, 1].
    """
    try:
        from core.mood_graph import mood_audio_target, cosine_similarity
        target = mood_audio_target(mood_name)
        if not target:
            return 0.0
        return cosine_similarity(audio_mean, target)
    except Exception:
        return 0.0
