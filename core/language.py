"""
language.py — Language detection for grouping songs by lyric language.

Uses langdetect (optional) on track name + artist name as a heuristic.
Not perfect — instrumental tracks and non-Latin scripts are imprecise,
but useful for separating e.g. Spanish/Portuguese/French/Korean music.
"""

from __future__ import annotations
import functools


# ISO 639-1 (+ common langdetect variants) → English name
LANGUAGE_DISPLAY: dict[str, str] = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "is": "Icelandic",
    "ga": "Irish",
    "cy": "Welsh",
    "pl": "Polish",
    "cs": "Czech",
    "sk": "Slovak",
    "sl": "Slovenian",
    "hr": "Croatian",
    "sr": "Serbian",
    "bs": "Bosnian",
    "ro": "Romanian",
    "hu": "Hungarian",
    "bg": "Bulgarian",
    "el": "Greek",
    "tr": "Turkish",
    "ru": "Russian",
    "uk": "Ukrainian",
    "et": "Estonian",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "sq": "Albanian",
    "mk": "Macedonian",
    "ar": "Arabic",
    "he": "Hebrew",
    "fa": "Persian",
    "ur": "Urdu",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
    "tl": "Tagalog",
    "fil": "Filipino",
    "sw": "Swahili",
    "af": "Afrikaans",
    "so": "Somali",
    "ca": "Catalan",
    "eu": "Basque",
    "gl": "Galician",
    "jw": "Javanese",
    "ko": "Korean",
    "ja": "Japanese",
    "zh": "Chinese",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "unknown": "Unknown",
}


@functools.lru_cache(maxsize=8192)
def detect_language(text: str) -> str:
    """
    Detect the language of a text string using langdetect.

    Results are cached (LRU, 8192 entries) so repeated calls for the same
    title+artist text are instant. langdetect is seeded for determinism.

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
        from langdetect import DetectorFactory
        DetectorFactory.seed = 0  # deterministic results
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
        # artists can be either list[str] or list[dict] (Spotify format)
        _names = []
        for a in artists[:2]:
            if isinstance(a, dict):
                _names.append(a.get("name", ""))
            elif isinstance(a, str):
                _names.append(a)
        artist_str = " ".join(filter(None, _names))
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
        result["other_languages"] = other

    return result


def language_display_name(lang_code: str) -> str:
    """
    Return the human-readable name for a language code.

    Args:
        lang_code: ISO 639-1 language code, or special bucket key.

    Returns:
        Display name string, or a readable fallback (never raw two-letter caps).
    """
    if lang_code in ("other", "other_languages"):
        return "Other Languages"
    raw = (lang_code or "").strip().lower()
    if not raw or raw == "unknown":
        return "Unknown"

    # Normalise zh variants
    norm = raw.replace("_", "-")
    if norm in ("zh-cn", "zh_cn"):
        return "Chinese (Simplified)"
    if norm in ("zh-tw", "zh_tw"):
        return "Chinese (Traditional)"

    base = norm.split("-")[0].split("_")[0]
    if len(base) >= 3:
        return raw.replace("-", " ").title()

    name = LANGUAGE_DISPLAY.get(norm) or LANGUAGE_DISPLAY.get(base)
    if name:
        return name

    # Unknown ISO 639-1 code — show "Code (xx)" instead of shouting "XX"
    return f"Other language ({base})"


def group_by_lyrics_language(
    tracks: list[dict],
    uri_to_lang: dict[str, str],
    min_tracks: int = 5,
) -> dict[str, list[str]]:
    """
    Group tracks using lyric-analysis language (from scan), not title heuristics.

    ``uri_to_lang`` maps Spotify URI → ISO 639-1 code (from ``lyrics.analyze_lyrics``).
    """
    raw: dict[str, list[str]] = {}
    for track in tracks:
        uri = track.get("uri")
        if not uri:
            continue
        lang = (uri_to_lang.get(uri) or "unknown").strip().lower() or "unknown"
        if lang == "unknown":
            continue
        raw.setdefault(lang, []).append(uri)

    result: dict[str, list[str]] = {}
    other: list[str] = []
    for lang, uris in raw.items():
        if len(uris) >= min_tracks:
            result[lang] = uris
        else:
            other.extend(uris)
    if other:
        result["other_languages"] = other
    return result
