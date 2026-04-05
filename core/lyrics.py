"""
lyrics.py — Public lyrics fetching and mood analysis (no API key required).

Primary source: lrclib.net — open-source, community-maintained, free.
  GET https://lrclib.net/api/get?artist_name={}&track_name={}
  Returns {plainLyrics, syncedLyrics, ...}  /  404 when not found.

Fallback source: lyrics.ovh — kept as a secondary source for coverage.
  GET https://api.lyrics.ovh/v1/{artist}/{title}

lrclib.net is significantly more reliable than lyrics.ovh:
  - Open source database maintained by the community
  - Well-structured API with proper HTTP semantics
  - No rate-limit surprises

WHAT THIS PRODUCES
==================
lyr_* mood tags per track, matching packs.json expected_tags via substring:
  lyr_sad · lyr_angry · lyr_love · lyr_hype · lyr_introspective
  lyr_euphoric · lyr_dark · lyr_party
  lyr_goodbye · lyr_homesick · lyr_nostalgic · lyr_hope · lyr_struggle · lyr_faith
  lyr_missing_you · lyr_revenge · lyr_money · lyr_freedom · lyr_night_drive

NOTE: These lyr_* tags are a SUPPLEMENT to proper tag sources (Last.fm,
AudioDB, MusicBrainz).  If Last.fm is configured, its crowd-sourced tags
(e.g. "sad", "chill", "dark") are far more accurate than lyric keyword
matching.  Lyrics analysis is the zero-key fallback only.

RATE LIMIT
==========
300ms gap between requests (~3 req/s) — conservative.

CACHE
=====
outputs/.lyrics_cache.json — persistent, shared across scans.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error

_ROOT          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH     = os.path.join(_ROOT, "outputs", ".lyrics_cache.json")
_LRCLIB_URL    = "https://lrclib.net/api/get"
_OVHLYRICS_URL = "https://api.lyrics.ovh/v1/"
_RATE_GAP      = 0.35   # ~2.8 req/s — stay under provider limits on long scans

_last_request_time: float = 0.0
_cache: dict | None = None


# ── Rate limiter ───────────────────────────────────────────────────────────────

def _rate_limit() -> None:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _RATE_GAP:
        time.sleep(_RATE_GAP - elapsed)
    _last_request_time = time.monotonic()


# ── Cache ──────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
            if isinstance(_cache, dict):
                return _cache
        except (json.JSONDecodeError, OSError):
            pass
    _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except OSError:
        pass


def _cache_key(artist: str, title: str) -> str:
    return f"{artist.lower().strip()}|{title.lower().strip()}"


# ── Mood keyword vocabulary ────────────────────────────────────────────────────

MOOD_KEYWORDS: dict[str, list[str]] = {
    # English — specific enough to be meaningful signal (avoid "go", "run", "think")
    "sad": [
        "crying", "tears", "broken heart", "alone tonight", "miss you", "goodbye",
        "heartbreak", "heartbroken", "depression", "grief", "mourning", "lonely",
        "sobbing", "weeping", "shattered", "devastated", "miserable",
        # Spanish
        "llorar", "lágrimas", "corazón roto", "soledad", "tristeza", "dolor",
        "perdido", "extrañar", "adiós", "depresión", "sufriendo",
        # French
        "pleurer", "larmes", "coeur brisé", "seul", "tristesse", "douleur",
        "manquer", "adieu", "dépression",
        # Portuguese
        "chorar", "lágrimas", "coração partido", "sozinho", "tristeza", "saudade",
    ],
    "angry": [
        "hatred", "rage", "furious", "revenge", "enemy", "destroy", "violence",
        "bloodshed", "wrath", "ruthless", "murderous", "vengeance",
        # Spanish
        "odio", "rabia", "furioso", "venganza", "destruir", "violencia", "matar",
        # French
        "haine", "rage", "furieux", "vengeance", "détruire", "violence",
        # Portuguese
        "ódio", "raiva", "furioso", "vingança", "destruir",
    ],
    "love": [
        "i love you", "falling in love", "kiss me", "beautiful girl", "forever together",
        "darling", "romance", "adore you", "cherish", "devoted", "soulmate",
        # Spanish
        "te amo", "te quiero", "amor", "besarte", "hermosa", "corazón", "enamorado",
        "romantico", "adorar", "cariño", "mi amor",
        # French
        "je t'aime", "amour", "t'embrasser", "belle", "chérie", "mon coeur",
        # Portuguese
        "eu te amo", "amor", "beijar", "linda", "querida", "coração",
        # Arabic transliterated
        "habibi", "habibti", "hayati", "albi",
    ],
    "hype": [
        "hustle", "flex", "drip", "squad", "grind", "trap", "stackin", "stacking",
        "no cap", "on god", "run it up", "gettin money", "getting money",
        "we lit", "turn up", "finna", "bussin", "slatt", "gang gang",
        # Spanish
        "dinero", "poder", "fuego", "gana", "arriba", "fiesta",
        # French
        "argent", "pouvoir", "feu",
        # Arabic transliterated
        "yalla", "wallah",
    ],
    "introspective": [
        "wondering", "searching my soul", "asking myself", "reflecting on",
        "looking back", "memories flood", "who am i", "what am i", "question everything",
        "lost myself", "finding myself", "inner peace", "meditation",
        # Spanish
        "reflexionar", "preguntarme", "alma", "recuerdos", "quién soy",
        # French
        "me demander", "réfléchir", "l'âme", "souvenirs",
        # Portuguese
        "refletir", "perguntar", "alma", "memórias",
    ],
    "euphoric": [
        "ecstasy", "euphoria", "paradise", "heaven on earth", "feeling alive",
        "on top of the world", "riding high", "blissful", "pure joy", "transcend",
        "free spirit", "soaring", "limitless", "unstoppable",
        # Spanish
        "éxtasis", "paraíso", "cielo", "libre", "alegría", "euforia",
        # French
        "extase", "paradis", "liberté", "joie",
        # Portuguese
        "êxtase", "paraíso", "liberdade", "alegria",
    ],
    "dark": [
        "darkness", "shadow", "haunted", "devil", "evil spirit", "demonic",
        "death comes", "bleed out", "hollow inside", "void inside", "sinister",
        "damnation", "cursed", "nightmare", "abyss", "torment",
        # Spanish
        "oscuridad", "sombra", "diablo", "maldito", "muerte", "tormento",
        # French
        "obscurité", "ombre", "diable", "maudit", "mort", "tourment",
        # Portuguese
        "escuridão", "sombra", "diabo", "maldito", "morte",
        # Japanese/anime transliterated
        "yami", "akuma",
    ],
    "party": [
        "let's party", "on the dancefloor", "dance floor", "nightclub", "shots all night",
        "turn it up", "good times tonight", "everybody dance", "we came to party",
        # Spanish
        "fiesta", "bailar", "baila", "club", "toda la noche",
        # French
        "fête", "danser", "boîte de nuit",
        # Portuguese
        "festa", "dançar", "balada",
        # Arabic transliterated
        "hafleh", "raqs",
    ],
    # ── Thematic (lyric-first packs; feed lyr_* tags for scorer) ───────────────
    "goodbye": [
        "farewell", "walking away", "last time i", "never again", "leaving you",
        "i'm leaving", "moving on", "it's over", "waved goodbye", "end of us",
        "walk away", "gone for good", "final goodbye", "let you go", "letting go",
        "closed this chapter", "endings", "said our goodbyes", "one last time",
        "adiós for good", "auf wiedersehen",
    ],
    "homesick": [
        "hometown", "going home", "back home", "miss home", "miles from home",
        "where i grew up", "old neighborhood", "childhood home", "family back home",
        "missing home", "roots run deep", "small town", "road that leads home",
    ],
    "nostalgic": [
        "remember when", "those days", "used to be", "way back when", "throwback",
        "memories of", "back then", "younger days", "old days", "miss those times",
        "golden days", "wish i could go back", "those summer nights",
    ],
    "hope": [
        "better days ahead", "hold on", "we'll be alright", "sun will rise",
        "brighter future", "still believe", "don't give up", "light at the end",
        "someday we will", "keep going", "not the end",
    ],
    "struggle": [
        "broke and", "struggling", "pay the rent", "working double", "barely getting by",
        "empty pockets", "hard times", "tired of fighting", "keep my head up",
    ],
    "faith": [
        "i pray", "prayer", "amen", "lord i", "god will", "blessed", "give it to god",
        "saved my soul", "church on sunday", "hallelujah", "jesus",
    ],
    "missing_you": [
        "wish you were here", "without you here", "thinking of you", "need you back",
        "come back to me", "read your messages", "still your side", "empty bed",
        "your side of", "ghost me", "left on read", "if you called",
        "te extraño", "manque", "saudade de você",
    ],
    "revenge": [
        "payback", "karma coming", "you will regret", "remember this", "plotting on",
        "get even", "watch your back", "you did this", "no forgiveness",
        "venganza", "revanche",
    ],
    "money": [
        "count the money", "count my money", "bankroll", "racks on", "bands on",
        "million dollars", "new whip", "cash out", "paid in full", "money long",
        "stack it up", "rich forever", "make it rain", "bag secured",
        "dinero", "argent", "grana",
    ],
    "freedom": [
        "run away with", "running away", "break these chains", "no chains", "open highway",
        "windows down", "nowhere to be", "leave this town", "starting over",
        "free at last", "finally free", "no turning back", "border crossing",
    ],
    "night_drive": [
        "dashboard lights", "city lights pass", "highway tonight", "3am on the",
        "empty road", "gas station glow", "rearview mirror", "neon blur",
        "driving nowhere", "passenger seat", "midnight miles",
    ],
    "family": [
        "mama", "momma", "mother", "father", "daddy", "dad", "family first",
        "my brother", "my sister", "grandma", "grandpa", "blood is thicker",
        "raised me", "my kids", "for my son", "for my daughter",
    ],
    "friends": [
        "day one", "ride or die", "my homies", "my crew", "best friend",
        "through thick and thin", "we still here", "loyalty", "real ones",
    ],
    "jealousy": [
        "jealous of", "green with envy", "you with her", "you with him",
        "watching you", "can't stand to see", "territory", "possessive",
    ],
    "summer": [
        "summer nights", "june", "july", "august heat", "pool party",
        "sun on my skin", "vacation", "beach with", "top down summer",
    ],
    "city": [
        "downtown", "skyline", "subway", "concrete jungle", "city never sleeps",
        "block", "corner store", "penthouse", "traffic lights",
    ],
    "ocean": [
        "ocean waves", "tide", "sail away", "anchor", "deep blue", "underwater",
        "shore", "island", "pirate",
    ],
}


# ── Language detection ─────────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    if not text or len(text.strip()) < 20:
        return "unknown"
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return "unknown"


# ── Lyrics fetching ────────────────────────────────────────────────────────────

def _clean(raw: str) -> str:
    """Remove section headers and collapse blank lines."""
    raw = re.sub(r"\[.*?\]", "", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def _fetch_lrclib(artist: str, title: str) -> tuple[str | None, bool]:
    """
    Fetch lyrics from lrclib.net (primary source — open-source, community-maintained).

    Returns (lyrics_or_None, should_cache).
    """
    params = urllib.parse.urlencode({"artist_name": artist, "track_name": title})
    url = f"{_LRCLIB_URL}?{params}"
    _rate_limit()
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Vibesort/1.0 (github.com/PapaKoftes/VibeSort)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw = data.get("plainLyrics") or ""
        # plainLyrics is clean unsynced text; use it directly
        lyrics = _clean(raw) if raw else None
        return lyrics, True   # definitive server answer
    except urllib.error.HTTPError as he:
        return None, he.code == 404   # 404 = confirmed not found
    except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
        return None, False    # transient failure — don't cache


def _fetch_ovh_fallback(artist: str, title: str) -> tuple[str | None, bool]:
    """
    Fetch lyrics from lyrics.ovh (fallback).

    Returns (lyrics_or_None, should_cache).
    """
    artist_enc = urllib.parse.quote(artist, safe="")
    title_enc  = urllib.parse.quote(title,  safe="")
    url = f"{_OVHLYRICS_URL}{artist_enc}/{title_enc}"
    _rate_limit()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Vibesort/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw = data.get("lyrics", "")
        lyrics = _clean(raw) if raw and not data.get("error") else None
        return lyrics, True
    except urllib.error.HTTPError as he:
        return None, he.code == 404
    except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
        return None, False


def fetch_lyrics(
    artist: str,
    title: str,
    genius_api_key: str | None = None,
) -> str | None:
    """
    Fetch lyrics for a track.

    Primary:  lrclib.net (open-source, community-maintained, reliable).
    Fallback: lyrics.ovh (if lrclib gives no lyrics and no definitive 404).
    Optional: Genius API when ``genius_api_key`` is set and prior sources miss.

    Returns cleaned lyrics string or None if not found. Results are cached.
    """
    if not artist or not title:
        return None

    cache = _load_cache()
    key   = _cache_key(artist, title)

    if key in cache:
        return cache[key].get("lyrics")

    lyrics, should_cache = _fetch_lrclib(artist, title)

    # Only fall back to lyrics.ovh if lrclib had a transient failure (not a 404)
    if lyrics is None and not should_cache:
        lyrics, should_cache = _fetch_ovh_fallback(artist, title)

    gkey = (genius_api_key or "").strip()
    if not gkey:
        try:
            import config as _cfg

            gkey = (getattr(_cfg, "GENIUS_API_KEY", "") or "").strip()
        except Exception:
            gkey = ""

    if lyrics is None and gkey:
        from core import genius as _genius_mod

        raw = _genius_mod.fetch_lyrics(gkey, artist, title)
        if raw:
            lyrics = _clean(raw)
            should_cache = True

    if should_cache:
        cache[key] = {"lyrics": lyrics}
        _save_cache()
    return lyrics


# ── Analysis ───────────────────────────────────────────────────────────────────

def analyze_lyrics(lyrics: str | None) -> dict:
    """
    Analyze lyrics for language and mood keyword scores.

    Returns:
        {
          "language":    str   — ISO 639-1 code or "unknown"
          "mood_scores": dict  — {mood: 0.0–1.0}
          "word_count":  int
          "explicit":    bool
        }
    """
    if not lyrics or len(lyrics.strip()) < 20:
        return {"language": "unknown", "mood_scores": {}, "word_count": 0, "explicit": False}

    text  = lyrics.lower()
    # Capture Latin + accented chars (covers EN/ES/FR/PT/DE/AR-romanized)
    words = re.findall(r"[a-záéíóúàâãêôõçüñäöß']+", text)

    mood_scores: dict[str, float] = {}
    for mood, keywords in MOOD_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            # Normalise by keyword count so multilingual keyword lists don't
            # artificially inflate scores relative to old single-language lists.
            mood_scores[mood] = round(min(hits / max(len(keywords), 1), 1.0), 4)

    explicit_words = {"fuck", "shit", "bitch", "nigga", "nigger", "ass"}
    return {
        "language":    _detect_language(lyrics),
        "mood_scores": mood_scores,
        "word_count":  len(words),
        "explicit":    bool(set(words) & explicit_words),
    }


def track_analysis(
    artist: str,
    title: str,
    genius_api_key: str | None = None,
) -> dict:
    """Fetch + analyze a single track. Fully cached."""
    cache = _load_cache()
    key   = _cache_key(artist, title)

    if key in cache and "analysis" in cache[key]:
        return cache[key]["analysis"]

    lyrics   = fetch_lyrics(artist, title, genius_api_key=genius_api_key)
    analysis = analyze_lyrics(lyrics)

    cache.setdefault(key, {})["analysis"] = analysis
    _save_cache()
    return analysis


def lyrics_tags(
    artist: str,
    title: str,
    genius_api_key: str | None = None,
) -> dict[str, float]:
    """
    Return lyr_* mood tags for a track compatible with Vibesort's tag system.
    e.g. {"lyr_sad": 0.8, "lyr_dark": 0.6}
    """
    scores = track_analysis(artist, title, genius_api_key=genius_api_key).get("mood_scores", {})
    return {f"lyr_{mood}": score for mood, score in scores.items()}


def enrich_library(
    tracks: list[dict],
    max_tracks: int = 200,
    progress_fn=None,
    genius_api_key: str | None = None,
) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """
    Batch-enrich tracks with lyrics mood tags.

    Args:
        tracks:      List of Spotify track dicts.
        max_tracks:  Hard cap to avoid overly long first runs.
        progress_fn: Optional callable(msg: str) for UI updates.

    Returns:
        (tags_map, lang_map)
          tags_map: {uri: {lyr_mood: score}}
          lang_map: {uri: language_code}
    """
    tags_map: dict[str, dict[str, float]] = {}
    lang_map: dict[str, str]              = {}
    processed = 0

    for track in tracks:
        if processed >= max_tracks:
            break
        uri    = track.get("uri", "")
        name   = track.get("name", "")
        artists = track.get("artists", [])
        artist  = (
            artists[0].get("name", "") if artists and isinstance(artists[0], dict)
            else (artists[0] if artists and isinstance(artists[0], str) else "")
        )

        if not (uri and name and artist):
            continue

        if progress_fn and processed % 25 == 0:
            progress_fn(f"Lyrics  {processed}/{min(len(tracks), max_tracks)}: {name[:30]}")

        analysis = track_analysis(artist, name, genius_api_key=genius_api_key)
        tags = {f"lyr_{m}": s for m, s in analysis.get("mood_scores", {}).items()}
        lang = analysis.get("language", "unknown")

        tags_map[uri] = tags
        lang_map[uri] = lang
        processed += 1

    return tags_map, lang_map
