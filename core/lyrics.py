"""
lyrics.py — Genius lyrics fetching and analysis.

Fetches lyrics to extract:
1. Language (from actual lyrics, far more reliable than title heuristic)
2. Topic keywords (what the song is about — complements audio features)
3. Basic mood signal from word presence

Requires: lyricsgenius (pip install lyricsgenius)
API key: get free at genius.com/api-clients

Cache: outputs/.lyrics_cache.json
"""

import json
import os
import re
from typing import Optional

CACHE_PATH = os.path.join("outputs", ".lyrics_cache.json")
_cache: dict | None = None

# Mood keyword sets — presence of these words in lyrics = signal
MOOD_KEYWORDS: dict[str, list[str]] = {
    "sad": ["cry", "tears", "broken", "alone", "hurt", "pain", "lost", "miss",
             "goodbye", "sorry", "dying", "depression", "grief", "mourn", "lonely"],
    "angry": ["hate", "rage", "angry", "mad", "kill", "fight", "war", "enemy",
               "destroy", "revenge", "furious", "damn", "violence", "attack"],
    "love": ["love", "heart", "kiss", "beautiful", "forever", "together", "darling",
              "baby", "romance", "hold", "embrace", "adore", "cherish"],
    "hype": ["go", "run", "grind", "hustle", "money", "flex", "win", "boss",
              "power", "fire", "lit", "drip", "gang", "squad", "trap"],
    "introspective": ["think", "wonder", "mind", "soul", "truth", "real", "question",
                       "believe", "understand", "reflect", "memory", "remind", "dream"],
    "euphoric": ["high", "fly", "rise", "free", "joy", "alive", "glow", "shine",
                  "celebrate", "dance", "ecstasy", "bliss", "heaven", "paradise"],
    "dark": ["dark", "shadow", "night", "black", "death", "ghost", "devil", "evil",
              "sin", "cold", "empty", "void", "silent", "hollow", "bleed"],
    "party": ["party", "dance", "club", "drink", "turn up", "weekend", "vibe",
               "good time", "celebrate", "shots", "groove", "move"],
}

# Language detection — we try langdetect on actual lyrics first
def _detect_language_from_text(text: str) -> str:
    if not text or len(text.strip()) < 20:
        return "unknown"
    try:
        from langdetect import detect, LangDetectException
        lang = detect(text)
        return lang
    except Exception:
        return "unknown"


def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    os.makedirs("outputs", exist_ok=True)
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
            return _cache
        except (json.JSONDecodeError, OSError):
            pass
    _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except OSError:
        pass


def _cache_key(artist: str, title: str) -> str:
    return f"{artist.lower().strip()}|{title.lower().strip()}"


def _genius_available() -> bool:
    try:
        import lyricsgenius
        return True
    except ImportError:
        return False


def connect(api_key: str) -> Optional[object]:
    """
    Connect to Genius API.

    Args:
        api_key: Genius API key from genius.com/api-clients

    Returns:
        Genius client or None.
    """
    if not api_key or not _genius_available():
        return None
    try:
        import lyricsgenius
        genius = lyricsgenius.Genius(
            api_key,
            timeout=10,
            retries=2,
            verbose=False,
            remove_section_headers=True,
            skip_non_songs=True,
        )
        return genius
    except Exception:
        return None


def _clean_lyrics(raw: str) -> str:
    """Strip contributor notes, headers, and excess whitespace from lyrics."""
    if not raw:
        return ""
    # Remove "X Contributors" prefix Genius adds
    raw = re.sub(r"^\d+\s+Contributors.*?\n", "", raw, flags=re.IGNORECASE)
    # Remove [Verse], [Chorus] etc.
    raw = re.sub(r"\[.*?\]", "", raw)
    # Collapse whitespace
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def fetch_lyrics(genius, artist: str, title: str) -> Optional[str]:
    """
    Fetch raw lyrics for a track.

    Args:
        genius: Genius client.
        artist: Artist name.
        title:  Track title.

    Returns:
        Cleaned lyrics string or None.
    """
    if genius is None or not artist or not title:
        return None

    cache = _load_cache()
    key = _cache_key(artist, title)
    if key in cache:
        return cache[key].get("lyrics")

    try:
        song = genius.search_song(title, artist, get_full_info=False)
        lyrics = _clean_lyrics(song.lyrics) if song and song.lyrics else None
        cache[key] = {"lyrics": lyrics}
        _save_cache()
        return lyrics
    except Exception:
        cache[key] = {"lyrics": None}
        _save_cache()
        return None


def analyze_lyrics(lyrics: Optional[str]) -> dict:
    """
    Analyze lyrics for language, mood keywords, and topic signals.

    Args:
        lyrics: Raw lyrics string.

    Returns:
        Dict with keys:
          language: ISO 639-1 code ("en", "pt", "es", etc.)
          mood_scores: {mood: score} where score is keyword hit rate [0, 1]
          word_count: int
          explicit: bool (presence of explicit keywords)
    """
    if not lyrics or len(lyrics.strip()) < 20:
        return {
            "language":    "unknown",
            "mood_scores": {},
            "word_count":  0,
            "explicit":    False,
        }

    text = lyrics.lower()
    words = re.findall(r"[a-záéíóúàâãêôõçüñ']+", text)
    word_count = len(words)
    word_set = set(words)

    # Language
    language = _detect_language_from_text(lyrics)

    # Mood keyword scores
    mood_scores: dict[str, float] = {}
    for mood, keywords in MOOD_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > 0:
            mood_scores[mood] = round(min(hits / len(keywords), 1.0), 4)

    # Explicit detection (simple)
    explicit_words = {"fuck", "shit", "bitch", "nigga", "nigger", "ass", "damn", "hell"}
    explicit = bool(word_set & explicit_words)

    return {
        "language":    language,
        "mood_scores": mood_scores,
        "word_count":  word_count,
        "explicit":    explicit,
    }


def track_analysis(genius, artist: str, title: str) -> dict:
    """
    Fetch and analyze a track's lyrics in one call.

    Returns full analysis dict from analyze_lyrics(), or empty dict on failure.
    Cached to disk.
    """
    cache = _load_cache()
    key = _cache_key(artist, title)

    # Check if we have analysis cached already
    if key in cache and "analysis" in cache[key]:
        return cache[key]["analysis"]

    lyrics = fetch_lyrics(genius, artist, title)
    analysis = analyze_lyrics(lyrics)

    # Update cache with analysis
    if key not in cache:
        cache[key] = {}
    cache[key]["analysis"] = analysis
    _save_cache()

    return analysis


def lyrics_tags(genius, artist: str, title: str) -> dict[str, float]:
    """
    Convenience: return lyrics mood scores as a {tag: weight} dict
    compatible with the rest of Vibesort's tag system.

    Tags are prefixed with "lyr_" to distinguish from playlist mining tags.

    Returns:
        {lyr_sad: 0.8, lyr_dark: 0.6, ...} or empty dict.
    """
    analysis = track_analysis(genius, artist, title)
    mood_scores = analysis.get("mood_scores", {})
    return {f"lyr_{mood}": score for mood, score in mood_scores.items()}


def enrich_library(
    genius,
    tracks: list[dict],
    max_tracks: int = 150,
) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """
    Batch-enrich a track list with lyrics analysis.

    Args:
        genius:     Genius client.
        tracks:     List of Spotify track dicts.
        max_tracks: Cap to avoid long wait times.

    Returns:
        Tuple of:
          tags_map:  {spotify_uri: {lyr_tag: weight}}
          lang_map:  {spotify_uri: language_code}
    """
    tags_map: dict[str, dict[str, float]] = {}
    lang_map: dict[str, str] = {}
    processed = 0

    for track in tracks:
        if processed >= max_tracks:
            break
        uri = track.get("uri", "")
        name = track.get("name", "")
        artists = track.get("artists", [])
        artist_name = artists[0].get("name", "") if artists else ""

        if not uri or not name or not artist_name:
            continue

        analysis = track_analysis(genius, artist_name, name)
        tags = {f"lyr_{mood}": score for mood, score in analysis.get("mood_scores", {}).items()}
        lang = analysis.get("language", "unknown")

        tags_map[uri] = tags
        lang_map[uri] = lang
        processed += 1

    return tags_map, lang_map
