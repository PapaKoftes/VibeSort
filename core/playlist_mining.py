"""
playlist_mining.py — Extract human meaning from Spotify playlist names.

Strategy (search-based):

For each mood, we search Spotify for public playlists using seed phrases from
packs.json.  Any user track that appears in those playlists gets tags derived
from the playlist name.  Tag weight is proportional to how many playlists the
track appears in and the playlist's relevance.

Bonus: PUBLIC PLAYLIST FINDER
  After mining we record, per mood, the top public playlists ranked by how many
  of the user's tracks they contain.  These surface on the Vibes page as
  "Playlists you'd fit right into."

Results are cached to <project_root>/outputs/.mining_cache.json (7-day TTL).
Delete the file to force a refresh.
"""

import re
import json
import os
import sys
import math
import time
import collections
import spotipy


def _print(*args, **kwargs) -> None:
    """Safe print that survives non-TTY stdout (Streamlit, pipes, Windows)."""
    try:
        print(*args, **kwargs)
    except (OSError, UnicodeEncodeError):
        try:
            kwargs.pop("end", None)
            kwargs.pop("flush", None)
            print(*args, file=sys.stderr)
        except Exception:
            pass
from core.anchors import get_anchor_ids
from core.profile import collapse_tags as _collapse_tags

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(_ROOT, "outputs", ".mining_cache.json")
CACHE_TTL_DAYS = 30  # tag.getTopTracks results are stable; 7-day was too aggressive

# Stopwords to remove when extracting tags from playlist names.
# Includes common functional words across major languages so non-English
# playlist names don't bloat the tag index with grammatical noise.
STOPWORDS = {
    # English
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "be", "been", "my",
    "your", "our", "their", "its", "this", "that", "these", "those", "it",
    "playlist", "music", "songs", "tracks", "mix", "hits", "vol",
    "best", "top", "new", "i", "you", "we", "they", "he", "she",
    # French
    "les", "des", "une", "pour", "avec", "dans", "sur", "par", "est",
    "que", "qui", "je", "tu", "il", "elle", "nous", "vous", "ils",
    "de", "du", "le", "la", "au", "aux",
    # Spanish
    "los", "las", "del", "con", "para", "por", "una", "unos", "que",
    "como", "más", "muy", "sus", "este", "esta",
    # German
    "die", "der", "das", "und", "mit", "von", "für", "auf", "ist",
    "ein", "eine", "nicht", "auch", "sind",
    # Portuguese
    "dos", "das", "com", "para", "por", "uma", "que", "mais", "como",
    "seu", "sua", "este", "essa",
    # Italian
    "dei", "della", "con", "per", "una", "che", "più", "molto",
    "questo", "questa",
    # Turkish
    "bir", "ile", "için", "var", "ve", "bu", "da", "de",
    # Arabic (transliterated common words)
    "min", "ila", "ala", "fee", "waw",
}

COMPOUND_TAGS = [
    # ── English compound mood phrases
    "late night", "night drive", "late night drive", "dark phonk",
    "gym rage", "deep focus", "chill vibes", "sad songs", "feel good",
    "good vibes", "golden hour", "after hours", "lo fi", "lo-fi",
    "study music", "work out", "warm up", "slow burn", "broken heart",
    "overthinking", "night time", "drive home", "summer vibes",
    "dark energy", "villain arc", "hype up", "turn up", "come down",
    "road trip", "open road", "night drive", "sad hours", "soft hours",
    "early morning", "late night", "feel good friday", "after party",
    "smoke session", "hard reset", "signal lost", "deep work",
    # ── French
    "rap français", "rap francais", "rap sombre", "nuit sombre",
    "chanson triste", "musique triste", "rap mélancolique",
    "rap dur", "soirée", "musique de nuit",
    # ── Arabic / MENA
    "trap arabe", "rap arabe", "arabic rap", "arabic trap",
    "rap egyptien", "arabic sad", "arabic drill",
    # ── German
    "deutschrap nacht", "deutschrap aggro",
    # ── Portuguese / Brazilian
    "phonk brasileiro", "baile funk", "funk brasileiro",
    "rap brasileiro", "trap brasileiro", "música brasileira",
    # ── Spanish
    "trap espanol", "rap en español", "canciones de desamor",
    "rap latino", "musica nocturna",
    # ── Turkish
    "türkçe rap", "gece müzik", "türkçe trap",
    # ── Hindi / South Asian
    "hindi sad songs", "bollywood sad", "desi trap",
    # ── Korean / Japanese
    "공부 음악", "감성 음악", "kpop sad", "jpop sad",
    "日本語ラップ", "夜の音楽",
    # ── Italian
    "trap italiano", "rap italiano",
    # ── Russian
    "русский рэп", "грустная музыка",
]

# ── Phrase boost weights ───────────────────────────────────────────────────────
# Compound tags that are highly diagnostic of a specific mood carry more signal
# than single generic words.  When a playlist name contains one of these phrases
# the tag gets this weight multiplier instead of the default 1.0.
#
# Scale: 1.0 = normal word, 2.0 = strong signal, 3.0 = diagnostic phrase.
PHRASE_BOOST: dict[str, float] = {
    # ── Night / drive
    "late_night_drive": 3.0,
    "night_drive":      2.5,
    "late_night":       2.0,
    "drive_home":       2.0,
    "midnight_drive":   2.5,
    "road_trip":        2.0,
    "open_road":        2.5,
    # ── Mood / feeling
    "sad_songs":        2.5,
    "sad_hours":        2.5,
    "feel_good":        2.0,
    "feel_good_friday": 2.0,
    "broken_heart":     2.5,
    "soft_hours":       2.5,
    "chill_vibes":      2.0,
    "good_vibes":       1.8,
    "dark_energy":      2.5,
    "overthinking":     2.5,
    "slow_burn":        2.0,
    "villain_arc":      3.0,
    "hype_up":          2.0,
    "after_hours":      2.0,
    "after_party":      2.0,
    "signal_lost":      2.0,
    "summer_vibes":     2.0,
    "night_time":       1.5,
    # ── Activity / context
    "dark_phonk":       3.0,
    "gym_rage":         3.0,
    "deep_focus":       2.5,
    "study_music":      2.5,
    "deep_work":        2.5,
    "work_out":         2.0,
    "warm_up":          1.5,
    "smoke_session":    2.5,
    "hard_reset":       2.5,
    "golden_hour":      2.5,
    "lo_fi":            2.2,
    "early_morning":    2.0,
    "turn_up":          1.8,
    "come_down":        2.0,
    "rainy_day":        2.2,
    "amapiano":         2.3,
    "anime":            2.0,
    "meditation":       2.0,
    "disco":            2.0,
    "techno":           2.0,
    "metal":            2.0,
    "punk":             2.0,
    "chillhop":         2.0,
    "classical":        1.8,
    "vaporwave":        2.2,
    "jpop":             2.0,
    # ── International compound phrases (same weight as English equivalents)
    "rap_français":         2.5,  "rap_francais":       2.5,
    "rap_sombre":           2.5,  "chanson_triste":     2.5,
    "musique_triste":       2.5,  "nuit_sombre":        2.0,
    "trap_arabe":           2.5,  "rap_arabe":          2.5,
    "arabic_rap":           2.5,  "arabic_trap":        2.5,
    "arabic_sad":           2.5,  "arabic_drill":       2.5,
    "phonk_brasileiro":     2.5,  "baile_funk":         2.0,
    "funk_brasileiro":      2.0,  "rap_brasileiro":     2.5,
    "trap_espanol":         2.5,  "rap_latino":         2.0,
    "türkçe_rap":           2.5,  "türkçe_trap":        2.5,
    "hindi_sad_songs":      2.5,  "bollywood_sad":      2.5,
    "desi_trap":            2.5,
    "trap_italiano":        2.5,  "rap_italiano":       2.5,
    "deutschrap_nacht":     2.5,  "deutschrap_aggro":   2.5,
    "kpop_sad":             2.5,  "jpop_sad":           2.5,
}

# ── Tag normalisation groups ───────────────────────────────────────────────────
# Many playlists use synonymous words that fragment meaning.
# "night" / "nights" / "midnight" / "late" all refer to the same concept.
# We map every VARIANT → CANONICAL so the scorer sees one unified signal.
#
# Mapping is applied AFTER compound-tag extraction so "late_night" is already
# captured as a boosted compound before its words are normalised individually.
TAG_GROUPS: dict[str, list[str]] = {
    # canonical   → [variants that collapse into it]
    "night":    ["nights", "nighttime", "midnight", "nocturnal", "late"],
    "drive":    ["driving", "driver", "cruise", "cruising", "road_trip"],
    "gym":      ["workout", "lifting", "training", "exercise", "fitness", "work_out"],
    "chill":    ["chilled", "chilling", "relax", "relaxed", "mellow", "laid_back"],
    "sad":      ["sadness", "crying", "cry", "tears", "heartbreak", "emotional"],
    "hype":     ["hyped", "fire", "lit", "turnt", "banger", "heat"],
    "dark":     ["darkness", "sinister", "eerie", "shadow", "noir", "shadowy"],
    "party":    ["parties", "clubbing", "rave", "festival", "dancefloor"],
    "love":     ["romance", "romantic", "lover", "crush", "affection"],
    "anger":    ["angry", "rage", "mad", "furious", "fury"],
    "focus":    ["studying", "concentration", "deep_work", "study_music", "work"],
    "phonk":    ["dark_phonk", "drift_phonk", "phonk_season"],
    "summer":   ["summertime", "sunshine", "sunny", "warm", "warmth"],
    "sleep":    ["sleeping", "sleepy", "ambient", "rest", "resting"],
    "morning":  ["sunrise", "dawn", "wakeup", "early_morning"],
    "workout":  ["preworkout", "pre_workout", "beast_mode", "gains", "sweat"],
}

# Build reverse lookup: variant → canonical
_VARIANT_TO_CANONICAL: dict[str, str] = {}
for _canonical, _variants in TAG_GROUPS.items():
    for _variant in _variants:
        _VARIANT_TO_CANONICAL[_variant] = _canonical


def normalize_tag(tag: str) -> str:
    """Return the canonical form of a tag, collapsing synonyms."""
    return _VARIANT_TO_CANONICAL.get(tag, tag)


# ── Semantic tag expansion ─────────────────────────────────────────────────────
# Compound/contextual tags imply richer meaning than their words alone.
# When a track has one of these tags, we automatically add the implied
# semantic tags at a reduced weight (SEMANTIC_WEIGHT × original weight).
# This gives the scorer more dimensions to match on without requiring
# every playlist to explicitly use those exact tag words.
#
# Example:
#   "late_night_drive" (w=1.0) → also adds "introspective" (w=0.5),
#   "dark" (w=0.5), "drive" (w=0.5), "night" (w=0.5)
#
# The expansion weight is deliberately low so it supplements, not replaces,
# real evidence.  A track with explicit "dark" tag still beats one that only
# inherited it via semantic expansion.

SEMANTIC_WEIGHT = 0.50   # weight of implied semantic tags vs source tag
BASIC_WEIGHT    = 0.35   # weight for simple-tag expansions (weaker than compound)

# ── Basic tag expansion (simple / atomic tags → implied concepts) ─────────────
# SEMANTIC_MAP covers compound phrases ("late_night_drive" → many concepts).
# BASIC_MAP handles atomic genre/vibe words — they also imply related dimensions
# but more loosely, so they get a lighter weight (BASIC_WEIGHT = 0.35 vs 0.50).
#
# This fills the gap where a track was tagged from playlists named simply
# "Phonk Playlist" or "Ambient Study" — single words that still carry meaning.
#
# Rule: only add implied tags that are clearly *derived from* the source tag,
# not everything loosely related.  The expansion should add signal, not noise.
BASIC_MAP: dict[str, list[str]] = {
    # ── Genre tags → implied mood/context
    "ambient":      ["chill", "focus", "sleep", "introspective"],
    "phonk":        ["dark", "drive", "night", "anger"],
    "drill":        ["dark", "anger", "night", "street"],
    "lofi":         ["chill", "focus", "study", "night"],
    "jazz":         ["chill", "night", "sophisticated"],
    "blues":        ["sad", "introspective", "chill"],
    "metal":        ["anger", "hype", "dark"],
    "acoustic":     ["chill", "introspective", "sad", "soft"],
    "country":      ["summer", "drive", "nostalgic"],
    "gospel":       ["worship", "uplift", "spiritual"],
    "trap":         ["dark", "hype", "night"],
    "rnb":          ["chill", "love", "night", "smooth"],
    "soul":         ["introspective", "love", "warm"],
    "indie":        ["introspective", "chill", "authentic"],
    "electronic":   ["hype", "night", "energy"],
    "classical":    ["focus", "ambient", "introspective"],
    "piano":        ["introspective", "chill", "sad", "ambient"],
    "guitar":       ["chill", "acoustic", "introspective"],

    # ── Mood/vibe tags → implied context
    "dark":         ["night", "introspective"],
    "chill":        ["relax", "soft", "gentle"],
    "hype":         ["energy", "pump"],
    "sad":          ["introspective", "slow"],
    "happy":        ["energy", "summer", "bright"],
    "angry":        ["dark", "hype"],
    "nostalgic":    ["introspective", "chill", "bittersweet"],
    "romantic":     ["love", "chill", "night"],
    "motivational": ["hype", "energy", "confident"],
    "melancholic":  ["sad", "introspective", "night"],
    "peaceful":     ["chill", "ambient", "sleep"],
    "intense":      ["energy", "hype", "focus"],
    "groovy":       ["dance", "chill", "happy"],
    "sexy":         ["love", "night", "smooth"],
    "rebellious":   ["anger", "dark", "hype"],
    "spiritual":    ["introspective", "ambient", "chill"],

    # ── Activity tags → implied mood
    "study":        ["focus", "chill", "ambient"],
    "gym":          ["hype", "energy", "anger"],
    "sleep":        ["chill", "ambient", "soft"],
    "party":        ["hype", "happy", "dance"],
    "workout":      ["hype", "energy", "gym"],
    "running":      ["hype", "energy", "drive"],
    "meditation":   ["ambient", "chill", "spiritual"],
    "coffee":       ["morning", "chill", "introspective"],
    "shower":       ["happy", "chill", "morning"],
    "cooking":      ["happy", "chill", "summer"],

    # ── Time/place tags → implied mood
    "morning":      ["soft", "chill", "happy"],
    "night":        ["introspective", "dark", "chill"],
    "summer":       ["happy", "energy", "warm"],
    "winter":       ["introspective", "chill", "sad"],
    "rain":         ["sad", "introspective", "chill"],
    "drive":        ["night", "introspective", "freedom"],
    "beach":        ["happy", "summer", "chill"],
    "city":         ["night", "energy", "dark"],
    "sunset":       ["nostalgic", "chill", "warm"],
}

SEMANTIC_MAP: dict[str, list[str]] = {
    # ── Night / drive
    "late_night_drive": ["introspective", "dark", "drive", "night"],
    "night_drive":      ["dark", "drive", "night"],
    "drive_home":       ["drive", "night", "chill"],
    "open_road":        ["drive", "summer", "freedom"],
    "road_trip":        ["drive", "summer", "freedom"],

    # ── Dark / villain
    "villain_arc":      ["dark", "anger", "confident"],
    "dark_energy":      ["dark", "anger", "night"],
    "dark_phonk":       ["dark", "phonk", "anger"],
    "signal_lost":      ["dark", "ambient", "eerie"],

    # ── Energy / gym
    "gym_rage":         ["hype", "anger", "gym"],
    "hype_up":          ["hype", "party", "energy"],
    "beast_mode":       ["hype", "gym", "anger"],
    "hard_reset":       ["anger", "hype", "gym"],

    # ── Chill / soft
    "chill_vibes":      ["chill", "relax", "mellow"],
    "slow_burn":        ["chill", "dark", "introspective"],
    "smoke_session":    ["chill", "dark", "night"],
    "soft_hours":       ["chill", "love", "gentle"],
    "sunday_soft":      ["chill", "morning", "gentle"],

    # ── Sad / emotional
    "sad_songs":        ["sad", "hollow", "emotional"],
    "sad_hours":        ["sad", "night", "hollow"],
    "broken_heart":     ["sad", "love", "hollow"],
    "overthinking":     ["introspective", "sad", "night"],

    # ── Happy / positive
    "feel_good":        ["hype", "happy", "summer"],
    "golden_hour":      ["warm", "happy", "summer"],
    "summer_vibes":     ["happy", "summer", "party"],
    "good_vibes":       ["happy", "chill", "summer"],
    "feel_good_friday": ["happy", "party", "hype"],

    # ── Night / ambient / introspective
    "midnight_clarity": ["introspective", "night", "sad"],
    "deep_focus":       ["focus", "chill", "ambient"],
    "deep_work":        ["focus", "chill", "ambient"],
    "study_music":      ["focus", "chill"],
    "after_hours":      ["night", "dark", "party"],
    "after_party":      ["party", "night", "chill"],
    "late_night":       ["night", "introspective"],
}


def _apply_semantic_expansion(
    tag_weights: dict[str, float],
) -> dict[str, float]:
    """
    Return a NEW tag_weights dict with semantic expansions merged in.

    Two expansion passes — higher-weight rules never overwritten by lower:

    Pass 1 — SEMANTIC_MAP (compound/contextual phrases):
      Each matching tag adds implied tags at SEMANTIC_WEIGHT (0.50) ×
      the source tag's weight.  Compound phrases carry more semantic weight
      because they are more specific ("late_night_drive" → 4 implied dims).

    Pass 2 — BASIC_MAP (atomic genre/vibe/activity tags):
      Each matching tag adds implied tags at BASIC_WEIGHT (0.35) ×
      the source tag's weight.  Atomic tags are less specific so their
      expansion is weaker — it supplements, never dominates.

    In both passes, an implied tag is only set if it is absent or currently
    weaker.  This ensures explicit evidence always beats inferred evidence.
    """
    expanded = dict(tag_weights)

    # Pass 1: compound/contextual phrases (stronger signal)
    for tag, weight in tag_weights.items():
        implied = SEMANTIC_MAP.get(tag)
        if not implied:
            continue
        impl_weight = weight * SEMANTIC_WEIGHT
        for impl_tag in implied:
            if expanded.get(impl_tag, 0.0) < impl_weight:
                expanded[impl_tag] = impl_weight

    # Pass 2: atomic tags (weaker signal — fills gaps, doesn't dominate)
    for tag, weight in tag_weights.items():
        implied = BASIC_MAP.get(tag)
        if not implied:
            continue
        impl_weight = weight * BASIC_WEIGHT
        for impl_tag in implied:
            if expanded.get(impl_tag, 0.0) < impl_weight:
                expanded[impl_tag] = impl_weight

    return expanded


# ── Script detection helpers ──────────────────────────────────────────────────
# Detect non-Latin scripts in playlist names and inject a language tag so the
# scorer can apply the correct macro genre boost even when the playlist name
# contains no Latin characters at all (e.g. "مزاج هادئ", "공부 음악", "夜の運転").
#
# Uses Unicode block ranges — no external dependency required.

def _detect_script_tags(text: str) -> list[str]:
    """
    Return language macro-tags inferred from Unicode scripts present in text.
    These are injected alongside normal word tags so the genre scorer can match
    international playlists even when the name contains no ASCII.
    """
    lang_tags: list[str] = []
    has_arabic    = any('\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F' for c in text)
    has_hebrew    = any('\u0590' <= c <= '\u05FF' for c in text)
    has_cyrillic  = any('\u0400' <= c <= '\u04FF' for c in text)
    has_greek     = any('\u0370' <= c <= '\u03FF' for c in text)
    has_devanagari= any('\u0900' <= c <= '\u097F' for c in text)  # Hindi/Sanskrit
    has_hangul    = any('\uAC00' <= c <= '\uD7AF' or '\u1100' <= c <= '\u11FF' for c in text)
    has_hiragana  = any('\u3040' <= c <= '\u309F' for c in text)
    has_katakana  = any('\u30A0' <= c <= '\u30FF' for c in text)
    has_cjk       = any('\u4E00' <= c <= '\u9FFF' for c in text)
    has_thai      = any('\u0E00' <= c <= '\u0E7F' for c in text)

    if has_arabic:    lang_tags.extend(["arabic", "mena"])
    if has_hebrew:    lang_tags.append("hebrew")
    if has_cyrillic:  lang_tags.extend(["russian", "cyrillic"])
    if has_greek:     lang_tags.append("greek")
    if has_devanagari:lang_tags.extend(["hindi", "indian"])
    if has_hangul:    lang_tags.extend(["korean", "kpop"])
    if has_hiragana or has_katakana:
                      lang_tags.extend(["japanese", "jpop"])
    if has_cjk and not has_hiragana and not has_katakana:
                      lang_tags.extend(["chinese", "mandarin"])
    if has_thai:      lang_tags.append("thai")

    # Latin-script language hints from common keyword patterns
    text_lower = text.lower()
    _fr_markers = {"français", "francais", "française", "chanson", "musique",
                   "nuit", "sombre", "mélancolie", "melancolie", "tristesse"}
    _de_markers = {"deutsch", "deutschrap", "nacht", "musik", "straße"}
    _pt_markers = {"brasileiro", "brasil", "baile", "funk brasileiro", "pagode",
                   "sertanejo", "forró"}
    _tr_markers = {"türkçe", "turkce", "türk", "gece", "müzik"}
    _es_markers = {"español", "espanol", "música", "musica", "canciones",
                   "noche", "reggaeton", "latin"}
    _it_markers = {"italiano", "italiana", "italiana", "musica italiana",
                   "trap italiano"}

    if any(m in text_lower for m in _fr_markers): lang_tags.append("french")
    if any(m in text_lower for m in _de_markers): lang_tags.append("german")
    if any(m in text_lower for m in _pt_markers): lang_tags.extend(["portuguese", "brazilian"])
    if any(m in text_lower for m in _tr_markers): lang_tags.append("turkish")
    if any(m in text_lower for m in _es_markers): lang_tags.append("spanish")
    if any(m in text_lower for m in _it_markers): lang_tags.append("italian")

    return lang_tags


# ── Tag extraction ─────────────────────────────────────────────────────────────

def extract_tags(text: str) -> list[str]:
    """
    Extract tags from a playlist name — language-agnostic.

    1. Compound phrases (COMPOUND_TAGS) are extracted first and underscore-joined.
    2. Unicode words (not just ASCII) are extracted and filtered.
    3. Script detection injects language macro-tags for non-Latin playlists.
    4. Each tag is normalised to its canonical form via normalize_tag().

    Using re.UNICODE ensures "rap français", "Türkçe Rap", "trap arabe" all
    tokenize correctly instead of being silently mangled by ASCII-only [a-z]+.

    Returns a deduplicated list in extraction order.
    """
    text_lower = text.lower()
    tags: list[str] = []

    # Step 1: compound phrase extraction (unchanged)
    for phrase in COMPOUND_TAGS:
        if phrase in text_lower:
            tags.append(normalize_tag(phrase.replace(" ", "_")))

    # Step 2: Unicode word extraction (replaces ASCII-only [a-z]+)
    # \w+ with re.UNICODE matches letters in any script: Latin, Arabic,
    # Cyrillic, Devanagari, Hangul, CJK, etc.
    words = re.findall(r"[^\W\d_]+", text_lower, re.UNICODE)
    for word in words:
        if word not in STOPWORDS and len(word) > 2:
            tags.append(normalize_tag(word))

    # Step 3: inject script/language tags for non-Latin content
    lang_tags = _detect_script_tags(text)
    tags.extend(lang_tags)

    return list(dict.fromkeys(tags))


def _tag_weight(tag: str) -> float:
    """Return the boost multiplier for a tag.  Compound/diagnostic phrases > 1.0."""
    return PHRASE_BOOST.get(tag, 1.0)


# ── Playlist fetching ──────────────────────────────────────────────────────────

def _search_playlists(sp: spotipy.Spotify, query: str, limit: int = 10) -> list[dict]:
    """
    Search for public playlists matching a query.
    NOTE: Spotify's search API returns PlaylistSimplified objects which do NOT
    include a followers field — we accept all results and don't filter on followers.
    """
    try:
        result = sp.search(q=query, type="playlist", limit=limit)
        playlists = result.get("playlists", {}).get("items", []) or []
        return [pl for pl in playlists if pl and pl.get("id")]
    except Exception:
        return []


def _playlist_track_uris(
    sp: spotipy.Spotify,
    playlist_id: str,
    max_tracks: int = 200,
    _blocked_flag: list | None = None,
    _budget: dict | None = None,
    _batch_gap: float = 0.12,
) -> list[str]:
    """Fetch track URIs from a playlist (up to max_tracks).

    _blocked_flag: optional single-element list used as an out-param.
    If the request is 403'd, _blocked_flag[0] is set to True.
    _budget: optional {"calls": int, "max": int} — counts each playlist_items page.
    """
    try:
        uris = []
        offset = 0
        while len(uris) < max_tracks:
            if _budget is not None and _budget["calls"] >= _budget["max"]:
                break
            if _budget is not None:
                _budget["calls"] += 1
            batch = sp.playlist_items(
                playlist_id,
                limit=min(100, max_tracks - len(uris)),
                offset=offset,
                additional_types=["track"],
            )
            items = (batch or {}).get("items", []) or []
            if not items:
                break
            for item in items:
                t = item.get("track")
                if t and t.get("uri") and t["uri"].startswith("spotify:track:"):
                    uris.append(t["uri"])
            if not batch.get("next"):
                break
            offset += 100
            time.sleep(max(_batch_gap, 0.05))
        return uris
    except Exception as _exc:
        _s = str(_exc)
        if ("403" in _s or "Forbidden" in _s) and _blocked_flag is not None:
            _blocked_flag[0] = True
        return []


# ── Cache ──────────────────────────────────────────────────────────────────────

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
        # Reject empty/broken caches (e.g. from previous failed runs)
        if not data.get("track_tags"):
            return None
        return data
    except Exception:
        return None


def _save_cache(data: dict) -> None:
    import datetime
    data["_timestamp"] = datetime.datetime.now().isoformat()
    try:
        from core.cache_io import atomic_write_json
        atomic_write_json(CACHE_PATH, data)
    except Exception:
        pass


# ── Last.fm tag chart mining (M1.3 — mood ground truth) ──────────────────────

def _load_mood_lastfm_tags() -> dict:
    """Load data/mood_lastfm_tags.json — mood → [last.fm tag, ...] mapping."""
    path = os.path.join(_ROOT, "data", "mood_lastfm_tags.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _mine_lastfm_tag_charts(
    user_tracks: list,
    user_uris: set,
    mood_packs: dict,
    api_key: str,
    mood_lastfm_tags: dict,
) -> dict:
    """
    Mine Last.fm tag.getTopTracks for each mood and cross-reference against the
    user's library.  Returns additions to track_context.

    Strategy:
      1. Build (artist_lower, title_lower) -> uri lookup from user library.
      2. For each mood in mood_lastfm_tags (up to 3 tags per mood):
           - Call lastfm.get_tag_top_tracks(tag, limit=100)
           - For each returned track: look up uri in library lookup
           - Matched track → add context entry with mood + tag signal
      3. Return {uri: [context_entry, ...]} for all matched library tracks.

    Unmatched tag-chart tracks are not stored — they provide no immediate signal
    but the matched ones lift the scored tracks to Top-N across that mood.

    Rate: ~210ms gap (enforced inside lastfm._api_get).
    First run for 110 moods × 3 tags: ~330 API calls ≈ 70s.
    All results cached in .lastfm_cache.json (no TTL — tag charts are stable).
    """
    if not api_key or not api_key.strip() or not mood_lastfm_tags:
        return {}

    try:
        import core.lastfm as _lf
    except ImportError:
        return {}

    # Build library lookup: (artist_lower, title_lower) -> uri
    lib_lookup: dict = {}
    for t in (user_tracks or []):
        uri    = t.get("uri", "")
        title  = (t.get("name") or "").lower().strip()
        arts   = t.get("artists") or []
        artist = (arts[0].get("name") or "").lower().strip() if arts else ""
        if uri and title and artist:
            lib_lookup[(artist, title)] = uri

    if not lib_lookup:
        return {}

    lf_cache    = _lf._load_cache()
    additions: dict = collections.defaultdict(list)
    fetched_tags: dict = {}          # tag_str -> [track dicts] — skip re-fetch
    tags_to_fetch_total = sum(min(len(v), 3) for v in mood_lastfm_tags.values())
    done = 0

    print(
        f"\n  Last.fm tag charts   fetching {tags_to_fetch_total} tags across"
        f" {len(mood_lastfm_tags)} moods (first run ~55s, then cached)"
    )

    for mood_name, tags in mood_lastfm_tags.items():
        if mood_name not in mood_packs:
            continue

        for tag in tags[:3]:   # cap at 3 tags per mood
            if tag not in fetched_tags:
                top = _lf.get_tag_top_tracks(
                    tag, limit=100, api_key=api_key, cache=lf_cache,
                )
                fetched_tags[tag] = top
                done += 1
                if done % 15 == 0 or done == tags_to_fetch_total:
                    print(f"  Last.fm tag charts   {done}/{tags_to_fetch_total} tags fetched")
            else:
                top = fetched_tags[tag]

            # Normalised tag string used as the track_context "tag" token.
            # This directly matches PHRASE_BOOST / BASIC_MAP vocabulary and
            # feeds into tag_score via the same semantic expansion pipeline.
            ctx_tag = tag.lower().replace(" ", "_")

            for track in top:
                a_low = (track.get("artist") or "").lower().strip()
                t_low = (track.get("title")  or "").lower().strip()
                uri   = lib_lookup.get((a_low, t_low))
                if uri and uri in user_uris:
                    additions[uri].append({
                        "playlist_id": f"lastfm:tag:{tag}",
                        "playlist":    f"Last.fm: {tag}",
                        "followers":   max(track.get("playcount", 1000), 1000),
                        "mood":        mood_name,
                        "tags":        [ctx_tag],
                    })

    _lf._save_cache(lf_cache)

    matched = len(additions)
    print(f"  Last.fm tag charts   {matched}/{len(user_uris)} library tracks matched")
    return dict(additions)


# ── Owned-playlist fallback ───────────────────────────────────────────────────

def _fuzzy_mood_match(text: str, mood_packs: dict) -> list:
    """
    Token overlap fuzzy match between playlist text and mood seed phrases.

    Returns [(mood_name, score), ...] for all moods with score >= 0.6.
    Uses token overlap: intersection / len(phrase_tokens).
    Handles multi-word phrases ("late night drive") correctly.
    """
    text_tokens = set(re.sub(r"[^\w\s]", " ", text.lower()).split())
    if not text_tokens:
        return []
    matches = []
    for mood_name, pack in mood_packs.items():
        seed_phrases = pack.get("seed_phrases") or [mood_name.lower()]
        best = 0.0
        for phrase in seed_phrases:
            phrase_tokens = set(re.sub(r"[^\w\s]", " ", phrase.lower()).split())
            if not phrase_tokens:
                continue
            overlap = len(text_tokens & phrase_tokens)
            score   = overlap / max(len(phrase_tokens), 1)
            best    = max(best, score)
        if best >= 0.6:
            matches.append((mood_name, best))
    return matches


def _mine_owned_playlists(
    sp: spotipy.Spotify,
    user_uris: set[str],
    *,
    max_playlist_fetches: int = 200,
    items_batch_gap: float = 0.12,
    mood_packs: dict = None,
) -> dict:
    """
    Mine the current user's OWN playlists for track→tag context.

    In Spotify's Development Mode, playlist_items is blocked for 3rd-party
    playlists but works fine for playlists owned by the authenticated user.
    This gives us free mood/genre signal from names like:
      "Sad Hours", "Late Night Drive", "Gym Rage", "Chill Sundays", etc.

    The tags extracted here feed directly into scorer.tag_score(), so even
    a handful of well-named playlists yields meaningful mood detection.

    Returns the same dict shape as mine() (without "blocked" key).
    """
    # Fetch the user's own playlists (names available from list call)
    try:
        user_id = sp.current_user()["id"]
    except Exception:
        return {
            "track_tags": {}, "track_context": {},
            "tag_index": {}, "mood_fit_playlists": {},
            "blocked": False,
        }

    owned: list[dict] = []
    offset = 0
    while True:
        try:
            batch = sp.current_user_playlists(limit=50, offset=offset)
            items = batch.get("items") or []
            if not items:
                break
            for pl in items:
                if pl and pl.get("id") and pl.get("owner", {}).get("id") == user_id:
                    owned.append(pl)
            if not batch.get("next"):
                break
            offset += 50
            time.sleep(0.08)
        except Exception:
            break

    if not owned:
        print("  Own playlists         0 owned playlists found")
        return {
            "track_tags": {}, "track_context": {},
            "tag_index": {}, "mood_fit_playlists": {},
            "blocked": False,
        }

    track_context: dict = collections.defaultdict(list)
    enriched_pl = 0
    _items_blocked = [False]   # out-param: set True on first 403
    _fetch_count = 0
    # uri → set[mood_name] from fuzzy playlist→mood matching (M1.9)
    uri_mood_matches: dict = collections.defaultdict(set)

    for pl in owned:
        if _fetch_count >= max_playlist_fetches:
            print(f"  Own playlists         fetch cap ({max_playlist_fetches}) — stopping")
            break
        pid     = pl.get("id", "")
        pl_name = pl.get("name") or ""
        pl_desc = (pl.get("description") or "").strip()

        # Combine name + description for richer tag extraction (M1.9)
        full_text = f"{pl_name} {pl_desc}".strip()
        tags      = extract_tags(full_text) or extract_tags(pl_name)
        if not tags:
            continue   # playlist name + description have no useful words — skip

        # Fuzzy match against mood seed phrases (M1.9)
        mood_hits = _fuzzy_mood_match(full_text, mood_packs) if mood_packs else []

        _fetch_count += 1
        uris = _playlist_track_uris(
            sp, pid, max_tracks=400, _blocked_flag=_items_blocked, _batch_gap=items_batch_gap,
        )
        time.sleep(max(items_batch_gap, 0.08))
        if _items_blocked[0]:
            break   # all playlist_items calls are blocked — stop early

        # Track-count quality proxy: larger playlists reflect more curation effort.
        # Caps at 2.0× for 100+ track playlists; barely above 1.0× for tiny ones.
        _pl_total = (pl.get("tracks") or {}).get("total") or 0
        _pl_quality = min(2.0, 1.0 + _pl_total / 100.0)

        matched = 0
        for uri in uris:
            if uri in user_uris:
                track_context[uri].append({
                    "playlist_id":   pid,
                    "playlist":      pl_name,
                    "followers":     0,
                    "mood":          None,
                    "tags":          tags,
                    "quality_mult":  _pl_quality,
                })
                for mood_name, _ in mood_hits:
                    uri_mood_matches[uri].add(mood_name)
                matched += 1
        if matched:
            enriched_pl += 1

    # Build weighted track_tags (phrase boost + semantic expansion)
    track_tags: dict = {}
    tag_index: dict  = collections.defaultdict(list)

    for uri, contexts in track_context.items():
        raw_weights: dict = collections.defaultdict(float)
        for ctx in contexts:
            _q = ctx.get("quality_mult", 1.0)
            for tag in ctx["tags"]:
                tag_weight = _tag_weight(tag)
                tag_weight *= 3.0 * _q  # owned playlists = strong user signal; larger playlists = higher quality
                raw_weights[tag] += tag_weight

        if raw_weights:
            # Apply semantic expansion before normalising
            expanded = _apply_semantic_expansion(dict(raw_weights))
            max_w = max(expanded.values())
            _built = {t: round(w / max_w, 4) for t, w in expanded.items()}
            _clusters = _collapse_tags(_built)
            track_tags[uri] = {**_built, **_clusters} if _clusters else _built
        for tag in track_tags.get(uri, {}):
            if uri not in tag_index[tag]:
                tag_index[tag].append(uri)

    # Inject mood_<slug>: 0.9 for tracks in fuzzy-matched playlists (M1.9)
    # Weight 0.9 = slightly below anchor (1.0) but above Last.fm chart (0.75)
    _mood_injected = 0
    for uri, moods in uri_mood_matches.items():
        if uri not in track_tags:
            track_tags[uri] = {}
        for mood_name in moods:
            _slug = mood_name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
            tag_key = f"mood_{_slug}"
            if track_tags[uri].get(tag_key, 0.0) < 0.9:
                track_tags[uri][tag_key] = 0.9
                _mood_injected += 1

    total_tagged = sum(1 for t in track_tags.values() if t)
    if _items_blocked[0]:
        print(
            f"  Own playlists mined   [playlist_items blocked by Spotify Dev Mode "
            f"— 0 tracks tagged from {len(owned)} playlists]"
        )
    else:
        _mood_str = f" · {_mood_injected} mood tags injected" if _mood_injected else ""
        print(
            f"  Own playlists mined   {total_tagged} tracks tagged "
            f"from {enriched_pl}/{len(owned)} playlists{_mood_str}"
        )

    return {
        "track_tags":              track_tags,
        "track_context":           {k: list(v) for k, v in track_context.items()},
        "tag_index":               dict(tag_index),
        "mood_fit_playlists":      {},
        "blocked":                 False,
        "playlist_items_blocked":  _items_blocked[0],
    }


# ── Editorial playlist catalogue ───────────────────────────────────────────────
# Spotify-curated editorial playlists mapped to mood names.
# IDs are stable public Spotify playlist IDs verified as of 2026.
# Add new entries here — the mining engine picks them up automatically.
# In Spotify Dev Mode, playlist_items will 403 for these (owned by "spotify");
# the function handles that gracefully and prints a single warning.

_EDITORIAL_PLAYLISTS: dict[str, list[str]] = {
    "Focus Flow":          ["37i9dQZF1DWZeKCadgRdKQ"],  # Deep Focus
    "Peaceful":            ["37i9dQZF1DX4sWSpwq3LiO"],  # Peaceful Piano
    "Happy Daze":          ["37i9dQZF1DXdPec7aLTmlC"],  # Happy Hits!
    "Melancholy":          ["37i9dQZF1DX3YSRoSdA634"],  # Life Sucks
    "Late Night":          ["37i9dQZF1DX4E3UdUs7fUx"],  # Late Night Vibes
    "Hype":                ["37i9dQZF1DWTggY0yqBxES"],  # Beast Mode
    "Chill Vibes":         ["37i9dQZF1DX4WYpdgoIcn6"],  # Chill Hits
    "Morning Coffee":      ["37i9dQZF1DX6ziVCJnEm59"],  # Morning Coffee
    "Workout":             ["37i9dQZF1DX70RN3TfWWJh"],  # Cardio
    "Party Mode":          ["37i9dQZF1DXaXB8fQg7xif"],  # Dance Party
    "Night Drive":         ["37i9dQZF1DX9tPFwDMOegx"],  # Night Drive
    "Bedroom Pop":         ["37i9dQZF1DWXIcbzpLauPS"],  # Bedroom Pop
    "Heartbreak":          ["37i9dQZF1DWXlBnHRBQ9PL"],  # Sad Beats
    "Jazz Vibes":          ["37i9dQZF1DXbITWG1ZJKYt"],  # Jazz Vibes
    "Lo-Fi Chill":         ["37i9dQZF1DWWQRwui0ExPn"],  # lofi beats
    "Indie Folk":          ["37i9dQZF1DWV7EzJly4jqt"],  # Indie Folk
    "R&B Mood":            ["37i9dQZF1DX4SBhb3fqCJd"],  # R&B Mood
    "Electronic Pulse":    ["37i9dQZF1DX6J754A1BISI"],  # Electronic Rising
    "Classical Focus":     ["37i9dQZF1DWV0gynK7G6pD"],  # Classical Focus
    "Confidence Boost":    ["37i9dQZF1DX3rxVfibe1L0"],  # Mood Booster
    "Soft Hours":          ["37i9dQZF1DX9XIFQuFvzM4"],  # Feelin Good
    "Slow Burn":           ["37i9dQZF1DWTvNyuk7TJ4o"],  # Slow Jams
    "Nostalgic":           ["37i9dQZF1DX4o1oenSJRJd"],  # All Out 80s
    "Alt Energy":          ["37i9dQZF1DX0UrRvztWcAU"],  # Rock This
    "Soul Stirring":       ["37i9dQZF1DX2UgsUIyTB2c"],  # Soul
    "Acoustic Calm":       ["37i9dQZF1DX504r1DvyvxG"],  # Acoustic Concentration
}


def _mine_editorial_playlists(
    sp: spotipy.Spotify,
    user_uris: set[str],
    mood_packs: dict,
    max_tracks: int,
    budget: dict,
    batch_gap: float,
) -> dict[str, list[dict]]:
    """
    Fetch Spotify editorial playlists and cross-reference with user's library.

    Returns track_context additions: {uri: [{playlist, followers, mood, tags}]}.
    Silently skips if all editorial playlists are 403-blocked (Dev Mode).
    """
    additions: dict[str, list[dict]] = collections.defaultdict(list)
    blocked_count = 0
    matched_count = 0
    fetched_count = 0

    # Build a quick reverse lookup: which moods does the user actually have?
    available_moods = set(mood_packs.keys())

    for mood_name, playlist_ids in _EDITORIAL_PLAYLISTS.items():
        # Only mine for moods that exist in the current pack
        if mood_name not in available_moods:
            continue
        if budget["calls"] >= budget["max"]:
            break

        for pid in playlist_ids:
            if budget["calls"] >= budget["max"]:
                break
            try:
                pl_meta = sp.playlist(pid, fields="name,followers,owner")
                time.sleep(0.1)
            except Exception:
                blocked_count += 1
                continue

            pl_name   = pl_meta.get("name", mood_name)
            followers = (pl_meta.get("followers") or {}).get("total", 0)
            tags      = extract_tags(pl_name)
            if not tags:
                tags = [mood_name.lower().replace(" ", "_")]

            try:
                track_uris = _playlist_track_uris(
                    sp, pid, max_tracks, _budget=budget, _batch_gap=batch_gap,
                )
                fetched_count += 1
            except Exception as exc:
                if "403" in str(exc) or "Forbidden" in str(exc):
                    blocked_count += 1
                continue

            for uri in track_uris:
                if uri in user_uris:
                    additions[uri].append({
                        "playlist_id": pid,
                        "playlist":    pl_name,
                        "followers":   followers,
                        "mood":        mood_name,
                        "tags":        tags,
                    })
                    matched_count += 1

            time.sleep(0.1)

    if blocked_count > 0 and fetched_count == 0:
        print("  Editorial playlists  blocked (Dev Mode) — skipped")
    elif fetched_count > 0:
        print(f"  Editorial playlists  {fetched_count} fetched · "
              f"{matched_count} track-mood matches")

    return dict(additions)


# ── Core mining ────────────────────────────────────────────────────────────────

def mine(
    sp: spotipy.Spotify,
    user_uris: set[str],
    mood_packs: dict,
    playlists_per_seed: int = 6,
    max_tracks_per_playlist: int | None = None,
    force_refresh: bool = False,
    user_tracks: list | None = None,
) -> dict:
    """
    Mine public Spotify playlists for track context.

    For each mood, searches Spotify using seed_phrases from packs.json.
    Any user track found in those playlists gets tags from the playlist name.

    Returns:
      {
        "track_tags":        {uri: {tag: weight}},
        "track_context":     {uri: [{playlist_name, followers, mood, tags}]},
        "tag_index":         {tag: [uri, ...]},
        "mood_fit_playlists":{mood: [{id, name, overlap_count, followers}]},
      }
    """
    if not force_refresh:
        cached = _load_cache()
        if cached:
            print("  Playlist mining       loaded from cache")
            cached.setdefault("blocked", False)
            cached.setdefault("playlist_items_blocked", cached.get("blocked", False))
            return cached

    import config as _cfg

    _mtp = (
        max_tracks_per_playlist
        if max_tracks_per_playlist is not None
        else int(getattr(_cfg, "MINING_MAX_TRACKS_PER_PLAYLIST", 100))
    )
    _max_calls = int(getattr(_cfg, "MINING_MAX_PLAYLIST_ITEMS_CALLS", 320))
    _budget = {"calls": 0, "max": _max_calls}
    _search_delay = float(getattr(_cfg, "MINING_SEARCH_DELAY", 0.38))
    _items_gap = float(getattr(_cfg, "MINING_PLAYLIST_ITEMS_GAP", 0.14))
    _batch_gap = float(getattr(_cfg, "MINING_ITEMS_BATCH_GAP", 0.12))
    _max_seeds = int(getattr(_cfg, "MINING_MAX_SEED_PHRASES", 2))
    _max_anchors = int(getattr(_cfg, "MINING_MAX_ANCHORS_PER_MOOD", 4))
    _max_owned = int(getattr(_cfg, "MINING_MAX_OWNED_PLAYLISTS", 48))

    print("  Playlist mining       starting (owned playlists first)...")

    # ── STEP 1: Always mine owned playlists first (highest-quality signal) ────
    # User-named playlists are zero-noise ground truth.  "Late Night Drive",
    # "Gym Rage", "Chill Sundays" — these are precise, intentional mood labels.
    # Random public search playlists are supplemental, not primary.
    own = _mine_owned_playlists(
        sp,
        user_uris,
        max_playlist_fetches=_max_owned,
        items_batch_gap=_batch_gap,
        mood_packs=mood_packs,   # M1.9: fuzzy mood matching
    )
    owned_context: dict = own.get("track_context", {})

    # Seed the main track_context with owned-playlist data (mood=None, no bias)
    track_context: dict[str, list[dict]] = collections.defaultdict(list)
    for uri, ctxs in owned_context.items():
        for ctx in ctxs:
            track_context[uri].append(ctx)

    # ── STEP 1.5: Last.fm tag.getTopTracks mood ground truth (M1.3) ──────────
    # Cross-reference Last.fm's community-curated mood playlists against the
    # user's library.  Matched tracks receive high-authority tag context that
    # feeds directly into tag_score.  Works even when Spotify Dev Mode blocks
    # all public playlist_items calls.
    _lf_api_key = (
        getattr(_cfg, "VIBESORT_LASTFM_API_KEY", "").strip()
        or getattr(_cfg, "LASTFM_API_KEY", "").strip()
    )
    _mood_lastfm_tags = _load_mood_lastfm_tags()
    if _lf_api_key and _mood_lastfm_tags and user_tracks:
        _chart_additions = _mine_lastfm_tag_charts(
            user_tracks, user_uris, mood_packs, _lf_api_key, _mood_lastfm_tags,
        )
        for uri, ctxs in _chart_additions.items():
            for ctx in ctxs:
                track_context[uri].append(ctx)
    elif not _lf_api_key:
        print("  Last.fm tag charts   skipped (no API key configured)")
    elif not user_tracks:
        print("  Last.fm tag charts   skipped (user_tracks not passed to mine())")

    # ── STEP 1.9: Editorial playlist mining (Spotify curated, high authority) ───
    # Spotify's own editorial playlists (e.g. "Deep Focus", "Peaceful Piano") are
    # the highest-quality mood signal available.  They are maintained by Spotify's
    # editorial team and have millions of followers.
    #
    # NOTE: In Spotify Dev Mode, playlist_items is blocked for playlists whose
    # owners are not registered in the app.  Spotify editorial playlists are
    # owned by "spotify" — so this step silently skips in Dev Mode.
    # In Extended Quota / Production, this works fully.
    _editorial_additions = _mine_editorial_playlists(
        sp, user_uris, mood_packs, _mtp, _budget, _batch_gap,
    )
    for uri, ctxs in _editorial_additions.items():
        for ctx in ctxs:
            track_context[uri].append(ctx)

    # ── STEP 2: Probe whether public playlist_items is accessible ─────────────
    # Spotify Dev Mode restricts playlist_items for playlists not owned by users
    # registered in the app.  Probe once before hammering all moods.
    _probe_playlists = _search_playlists(sp, "chill vibes", limit=3)
    time.sleep(_search_delay)
    _probe_blocked = False
    for _pp in _probe_playlists:
        _probe_id = _pp.get("id")
        if not _probe_id:
            continue
        try:
            if _budget["calls"] < _budget["max"]:
                _budget["calls"] += 1
            sp.playlist_items(_probe_id, limit=1, additional_types=["track"])
            time.sleep(_batch_gap)
        except Exception as _pe:
            if "403" in str(_pe) or "Forbidden" in str(_pe):
                _probe_blocked = True
        break  # only probe once

    fetched_ids: set[str] = set()   # defined here so final print is always valid
    _budget_hit = False

    if _probe_blocked:
        print("  [warn] public playlist_items blocked (Dev Mode) — "
              "using owned playlists only")
        # Still build and return from owned data collected above
    else:
        # ── STEP 3: Supplement with public search (secondary signal) ──────────
        total_moods = len(mood_packs)
        processed_moods = 0

        for mood_name, pack in mood_packs.items():
            if _budget["calls"] >= _budget["max"]:
                _budget_hit = True
                break
            processed_moods += 1
            seed_phrases = pack.get("seed_phrases", [])
            if not seed_phrases:
                seed_phrases = [mood_name.lower()]

            queries_used = seed_phrases[:_max_seeds]
            _print(
                f"  Searching             {processed_moods}/{total_moods}: {mood_name[:30]:<30}",
            )

            # Prepend anchor playlists for this mood (curated, high-quality signal)
            for anchor_id in get_anchor_ids(mood_name)[:_max_anchors]:
                if _budget["calls"] >= _budget["max"]:
                    _budget_hit = True
                    break
                if anchor_id in fetched_ids:
                    continue
                try:
                    anchor_pl = sp.playlist(anchor_id)
                    time.sleep(_items_gap)
                except Exception:
                    continue
                if not anchor_pl:
                    continue
                anchor_name = anchor_pl.get("name", "")
                anchor_followers = (anchor_pl.get("followers") or {}).get("total", 0)
                anchor_tags = extract_tags(anchor_name)
                if not anchor_tags:
                    continue
                fetched_ids.add(anchor_id)
                anchor_uris = _playlist_track_uris(
                    sp, anchor_id, _mtp, _budget=_budget, _batch_gap=_batch_gap,
                )
                time.sleep(_items_gap)
                for uri in anchor_uris:
                    if uri in user_uris:
                        track_context[uri].append({
                            "playlist_id": anchor_id,
                            "playlist":    anchor_name,
                            "followers":   anchor_followers,
                            "mood":        mood_name,
                            "tags":        anchor_tags,
                        })
            if _budget_hit:
                break

            for query in queries_used:
                if _budget["calls"] >= _budget["max"]:
                    _budget_hit = True
                    break
                playlists = _search_playlists(sp, query, limit=playlists_per_seed)
                time.sleep(_search_delay)

                for pl in playlists:
                    if _budget["calls"] >= _budget["max"]:
                        _budget_hit = True
                        break
                    pid = pl.get("id")
                    if not pid or pid in fetched_ids:
                        continue

                    pl_name   = pl.get("name", "")
                    followers = (pl.get("followers") or {}).get("total", 0)
                    tags      = extract_tags(pl_name)

                    if not tags:
                        continue

                    fetched_ids.add(pid)
                    uris = _playlist_track_uris(
                        sp, pid, _mtp, _budget=_budget, _batch_gap=_batch_gap,
                    )
                    time.sleep(_items_gap)

                    for uri in uris:
                        if uri in user_uris:
                            track_context[uri].append({
                                "playlist_id": pid,
                                "playlist":    pl_name,
                                "followers":   followers,
                                "mood":        mood_name,
                                "tags":        tags,
                            })
                if _budget_hit:
                    break
            if _budget_hit:
                break

        if _budget_hit:
            print(
                f"\r  Search stopped early  playlist_items budget ({_max_calls}) · "
                f"{len(fetched_ids)} playlists          "
            )
        else:
            print(f"\r  Search complete       {len(fetched_ids)} playlists · "
                  f"{len(track_context)} tracks matched          ")

    # ── Build weighted tag scores (phrase boost + semantic expansion) ─────────
    track_tags: dict[str, dict[str, float]] = {}
    tag_index: dict[str, list[str]] = collections.defaultdict(list)

    for uri, contexts in track_context.items():
        raw_weights: dict[str, float] = collections.defaultdict(float)
        for ctx in contexts:
            followers = ctx.get("followers", 1000)
            if ctx.get("mood") is None:  # owned playlists have mood=None
                authority = 3.5  # owned playlists: strong user signal, bypass log formula
            else:
                authority = math.log10(max(followers, 1) + 1)
            for tag in ctx["tags"]:
                # Phrase-boosted: "late_night_drive" (3×) > "drive" (1×)
                # Authority-weighted: larger playlists contribute more signal
                raw_weights[tag] += _tag_weight(tag) * authority

        if raw_weights:
            # Semantic expansion: "late_night_drive" implies "introspective",
            # "dark", "drive", "night" at 0.5× weight — adds depth without ML
            expanded = _apply_semantic_expansion(dict(raw_weights))
            max_w = max(expanded.values())
            _built = {t: round(w / max_w, 4) for t, w in expanded.items()}
            # Merge in canonical cluster names so scoring vocabulary aligns
            _clusters = _collapse_tags(_built)
            track_tags[uri] = {**_built, **_clusters} if _clusters else _built
        else:
            track_tags[uri] = {}
        for tag in track_tags[uri]:
            if uri not in tag_index[tag]:
                tag_index[tag].append(uri)

    # ── Public playlist finder: top playlists per mood by user overlap ────────
    mood_fit_playlists: dict[str, list[dict]] = collections.defaultdict(list)
    pl_overlap_count: dict[str, dict] = {}  # key → {mood, name, followers, count}

    for uri, contexts in track_context.items():
        for ctx in contexts:
            pid = ctx.get("playlist_id", "")
            if not pid:
                continue
            mood = ctx["mood"]
            key  = f"{pid}::{mood}"
            if key not in pl_overlap_count:
                pl_overlap_count[key] = {
                    "id":        pid,
                    "name":      ctx["playlist"],
                    "followers": ctx["followers"],
                    "mood":      mood,
                    "count":     0,
                }
            pl_overlap_count[key]["count"] += 1

    for entry in pl_overlap_count.values():
        mood_fit_playlists[entry["mood"]].append(entry)

    for mood_name in mood_fit_playlists:
        mood_fit_playlists[mood_name].sort(key=lambda x: -x["count"])
        mood_fit_playlists[mood_name] = mood_fit_playlists[mood_name][:5]

    # ── Inject mood_* confidence signal for Last.fm tag-chart matches ─────────
    # Tracks matched via tag charts have context entries with mood set and
    # playlist_id starting with "lastfm:tag:".  The _signal_confidence()
    # scorer gives +0.45 for mood_* tags but none are produced when
    # playlist_items is blocked.  Inject here so chart-matched tracks get
    # the full confidence boost regardless of Spotify API restrictions.
    _chart_mood_injected = 0
    for uri, contexts in track_context.items():
        for ctx in contexts:
            _mood = ctx.get("mood")
            if _mood and str(ctx.get("playlist_id", "")).startswith("lastfm:tag:"):
                _slug    = _mood.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
                _tag_key = f"mood_{_slug}"
                _entry   = track_tags.setdefault(uri, {})
                if _entry.get(_tag_key, 0.0) < 0.9:
                    _entry[_tag_key] = 0.9
                    _chart_mood_injected += 1
    if _chart_mood_injected:
        print(f"  Tag-chart mood boost  {_chart_mood_injected} mood_* tags injected for chart-matched tracks")

    total_tagged = sum(1 for t in track_tags.values() if t)
    print(f"  Mining complete       {len(fetched_ids)} playlists · "
          f"{total_tagged}/{len(user_uris)} tracks tagged")

    _own_items_blocked = own.get("playlist_items_blocked", False)
    result = {
        "track_tags":              track_tags,
        "track_context":           {k: v for k, v in track_context.items()},
        "tag_index":               dict(tag_index),
        "mood_fit_playlists":      dict(mood_fit_playlists),
        "blocked":                 _probe_blocked,
        "playlist_items_blocked":  _probe_blocked or _own_items_blocked,
    }
    _save_cache(result)
    return result


def mood_observed_tag_weights(track_context: dict, mood_name: str) -> dict[str, float]:
    """
    Aggregate tag weights from mining contexts tied to a specific mood
    (public/anchor playlists labeled with that mood). Used to blend real
    playlist vocabulary into expected tags via scorer.combine_expected_tags.

    The result is run through collapse_tags so it uses the same canonical
    cluster vocabulary as track_tags profiles — preventing "midnight"/"driving"
    style vocabulary mismatches when the scorer compares expected tags against
    track tag_clusters.
    """
    raw_weights: dict[str, float] = collections.defaultdict(float)
    for uri, ctxs in track_context.items():
        for ctx in ctxs:
            if ctx.get("mood") != mood_name:
                continue
            followers = ctx.get("followers", 1000)
            authority = math.log10(max(followers, 1) + 1)
            for tag in ctx.get("tags", []):
                raw_weights[tag] += _tag_weight(tag) * authority

    raw = dict(raw_weights)
    # Normalize to [0,1] then collapse to canonical cluster names
    if raw:
        max_w = max(raw.values())
        if max_w > 0:
            raw = {t: round(w / max_w, 4) for t, w in raw.items()}
    collapsed = _collapse_tags(raw)
    # Merge: collapsed cluster names take precedence; raw raw tags fill rest
    return {**raw, **collapsed} if collapsed else raw
