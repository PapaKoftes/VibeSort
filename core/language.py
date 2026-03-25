"""
language.py — Language detection for grouping songs by lyric language.

Uses langdetect (optional) on track name + artist name as a heuristic.
Not perfect — instrumental tracks and non-Latin scripts are imprecise,
but useful for separating e.g. Spanish/Portuguese/French/Korean music.
"""

from __future__ import annotations


LANGUAGE_DISPLAY: dict[str, str] = {
    "pt":      "Portuguese",
    "es":      "Spanish",
    "fr":      "French",
    "de":      "German",
    "ko":      "Korean",
    "ja":      "Japanese",
    "ar":      "Arabic",
    "en":      "English",
    "it":      "Italian",
    "ru":      "Russian",
    "tr":      "Turkish",
    "nl":      "Dutch",
    "pl":      "Polish",
    "sv":      "Swedish",
    "zh-cn":   "Chinese (Simplified)",
    "zh-tw":   "Chinese (Traditional)",
    "hi":      "Hindi",
    "unknown": "Unknown",
}


def detect_language(text: str) -> str:
    """
    Detect the language of a text string using langdetect.

    Args:
        text: Any string (track name, artist name, etc.)

    Returns:
        ISO 639-1 language code ("en", "pt", "es", etc.),
        or "unknown" on failure or if langdetect is not installed.
    """
    if not text or not text.strip():
        return "unknown"
    try:
        from langdetect import detect, LangDetectException
        try:
            return detect(text)
        except LangDetectException:
            return "unknown"
    except ImportError:
        return "unknown"
    except Exception:
        return "unknown"


def track_language(track: dict) -> str:
    """
    Attempt to detect the language of a track from its name and artist.

    Uses track name + artist name as a combined hint. This is imprecise
    for short English-looking titles but works well for non-English tracks.

    Args:
        track: Dict with at least "name" and optionally "artists" (list of str).

    Returns:
        ISO 639-1 language code, or "unknown".
    """
    name = track.get("name", "")
    artists = track.get("artists", [])
    if isinstance(artists, list):
        artist_str = " ".join(artists[:2])
    else:
        artist_str = str(artists)

    combined = f"{name} {artist_str}".strip()
    if not combined:
        return "unknown"

    # Heuristic: short English-looking names are hard to detect — skip them
    if len(combined) < 8:
        return "unknown"

    return detect_language(combined)


def group_by_language(
    tracks: list[dict],
    min_tracks: int = 3,
) -> dict[str, list[str]]:
    """
    Group a list of tracks by detected language, returning URIs per language.

    Args:
        tracks:     List of track dicts with "uri", "name", "artists".
        min_tracks: Minimum tracks for a language group to be included.
                    Languages with fewer tracks are grouped under "other".

    Returns:
        Dict of {lang_code: [uri, ...]} for groups meeting min_tracks.
        The "other" key collects underrepresented languages.
    """
    raw: dict[str, list[str]] = {}

    for track in tracks:
        uri = track.get("uri")
        if not uri:
            continue
        lang = track_language(track)
        if lang not in raw:
            raw[lang] = []
        raw[lang].append(uri)

    # Filter by minimum track count
    result: dict[str, list[str]] = {}
    other: list[str] = []
    for lang, uris in raw.items():
        if len(uris) >= min_tracks:
            result[lang] = uris
        else:
            other.extend(uris)

    if other:
        result["other"] = other

    return result


def language_display_name(lang_code: str) -> str:
    """
    Return the human-readable name for a language code.

    Args:
        lang_code: ISO 639-1 language code.

    Returns:
        Display name string, or the code itself if not in LANGUAGE_DISPLAY.
    """
    return LANGUAGE_DISPLAY.get(lang_code.lower(), lang_code.upper())
