"""
profile.py — Build unified track profiles combining all signal layers.

A track profile unifies:
  Layer 1: audio_vector    (Spotify API or metadata_proxy heuristics, normalized)
  Layer 2: genres          (raw Spotify genres from artist)
  Layer 3: macro_genres    (mapped to ~15 broad categories)
  Layer 4: tags            (from playlist mining, weighted)
  Layer 5: popularity      (Spotify popularity score 0-100)

The audio vector is: [energy, valence, danceability, tempo_norm,
                      acousticness, instrumentalness]
Tempo is normalized by dividing by 200 (covers ~60-200 BPM range).

Extra fields stored alongside (do NOT change audio_vector shape):
  lyric_mood   — dict of {mood_label: weight} extracted from lyr_* tags
  release_year — int, year extracted from album.release_date (0 if missing)
  _features    — raw Spotify features dict for scorer access
"""

from core.genre import to_macro

AUDIO_KEYS = ["energy", "valence", "danceability", "acousticness", "instrumentalness"]

# Sentinel value emitted when Spotify audio features are unavailable.
# scorer.py detects this exact value to avoid treating it as real data.
_NEUTRAL_AUDIO = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]


def _audio_vector(features: dict) -> list[float]:
    """
    Normalized 6-dim audio vector.

    Returns the _NEUTRAL_AUDIO sentinel ([0.5]*6) when features are absent
    so scorer.py can detect and zero-out the audio score for those tracks.
    """
    if not features:
        return list(_NEUTRAL_AUDIO)
    tempo_norm = min(features.get("tempo", 120) / 200.0, 1.0)
    return [
        features.get("energy",           0.5),
        features.get("valence",          0.5),
        features.get("danceability",     0.5),
        tempo_norm,
        features.get("acousticness",     0.5),
        features.get("instrumentalness", 0.0),
    ]


def _confidence(tags: dict, raw_genres: list, features: dict, audio_vector_source: str) -> dict:
    """
    Compute a per-track confidence score for each signal layer.

    Tags confidence  = how many distinct tags the track has (capped at 1.0 at 10+).
    Genres confidence = 1.0 if at least one genre is known, 0.0 otherwise.
    Audio confidence  = 1.0 for Spotify API features; metadata proxy uses _proxy_confidence;
                        0.0 for neutral sentinel only.
    Overall           = weighted mean of the three (tags dominant).
    """
    tag_conf   = min(len(tags) / 10.0, 1.0) if tags else 0.0
    genre_conf = 1.0 if raw_genres else 0.0
    if audio_vector_source == "spotify":
        audio_conf = 1.0 if features else 0.0
    elif audio_vector_source == "metadata_proxy":
        audio_conf = float(features.get("_proxy_confidence", 0.35))
    else:
        audio_conf = 0.0
    overall    = round(0.60 * tag_conf + 0.25 * genre_conf + 0.15 * audio_conf, 4)
    return {
        "tags":    round(tag_conf,   4),
        "genres":  genre_conf,
        "audio":   round(audio_conf, 4),
        "overall": overall,
    }


def _audio_vector_source(features: dict, audio_vector: list[float]) -> str:
    """spotify | metadata_proxy | neutral"""
    if audio_vector == list(_NEUTRAL_AUDIO):
        return "neutral"
    if features.get("_source") == "metadata_proxy":
        return "metadata_proxy"
    return "spotify"


def _lyric_mood(track_tags: dict, uri: str) -> dict[str, float]:
    """Extract lyr_* tags into a {mood_label: weight} dict for the given URI."""
    return {
        k[4:]: v
        for k, v in track_tags.get(uri, {}).items()
        if k.startswith("lyr_")
    }


def _release_year(track: dict) -> int:
    """Extract the release year from track['album']['release_date']. Returns 0 if missing."""
    release_date = track.get("album", {}).get("release_date", "")
    if release_date:
        try:
            return int(str(release_date)[:4])
        except (ValueError, TypeError):
            pass
    return 0


def build(
    track: dict,
    artist_genres_map: dict[str, list[str]],
    audio_features_map: dict[str, dict],
    track_tags: dict[str, dict[str, float]],
) -> dict:
    """
    Build a full profile for one track.

    Returns:
      {
        uri, name, artists,
        audio_vector,       # always 6-dim — do not change shape
        raw_genres, macro_genres,
        tags,
        popularity,
        lyric_mood,         # {mood_label: weight} from lyr_* tags
        release_year,       # int year, 0 if unknown
        _features,          # raw Spotify features dict
      }
    """
    uri = track.get("uri", "")
    features = audio_features_map.get(uri, {})

    raw_genres: list[str] = []
    macro_seen: set[str] = set()
    macro_genres: list[str] = []
    for artist in track.get("artists", []):
        for genre in artist_genres_map.get(artist["id"], []):
            if genre not in raw_genres:
                raw_genres.append(genre)
            macro = to_macro(genre)
            if macro not in macro_seen:
                macro_seen.add(macro)
                macro_genres.append(macro)

    tags = track_tags.get(uri, {})
    vec = _audio_vector(features)
    av_src = _audio_vector_source(features, vec)
    return {
        "uri":          uri,
        "name":         track.get("name", ""),
        "artists":      [a.get("name", "") for a in track.get("artists", [])],
        "audio_vector": vec,
        "audio_vector_source": av_src,
        "raw_genres":   raw_genres,
        "macro_genres": [g for g in macro_genres if g != "Other"] or ["Other"],
        "tags":         tags,
        "tag_clusters": collapse_tags(tags),
        "popularity":   track.get("popularity", 50),
        "lyric_mood":   _lyric_mood(track_tags, uri),
        "release_year": _release_year(track),
        "_features":    features,   # kept for scorer access
        "confidence":   _confidence(tags, raw_genres, features, av_src),
    }


def build_all(
    tracks: list[dict],
    artist_genres_map: dict[str, list[str]],
    audio_features_map: dict[str, dict],
    track_tags: dict[str, dict[str, float]],
) -> dict[str, dict]:
    """Build profiles for all tracks. Returns {uri: profile}."""
    profiles: dict[str, dict] = {}
    for track in tracks:
        uri = track.get("uri")
        if uri:
            profiles[uri] = build(track, artist_genres_map, audio_features_map, track_tags)
    return profiles


def user_audio_mean(profiles: dict[str, dict]) -> list[float]:
    """
    Mean audio vector over tracks with non-neutral vectors (Spotify or metadata proxy).
    Neutral [0.5]*6 sentinels are excluded.
    """
    vectors = [
        p["audio_vector"]
        for p in profiles.values()
        if p["audio_vector"] != _NEUTRAL_AUDIO
    ]
    if not vectors:
        return list(_NEUTRAL_AUDIO)
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(6)]


def user_tag_preferences(profiles: dict[str, dict]) -> dict[str, float]:
    """Aggregate tag weights across the library to understand preferred vibes.

    Numeric pseudo-tags (dz_bpm, vader_valence) store raw floats far outside
    [0, 1] and are excluded — including them would corrupt taste_adaptation_boost
    for any track where they are the dominant or only tag.
    """
    _NUMERIC_PSEUDO = frozenset({"dz_bpm", "vader_valence"})
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for p in profiles.values():
        for tag, w in p["tags"].items():
            if tag in _NUMERIC_PSEUDO:
                continue
            totals[tag] = totals.get(tag, 0) + w
            counts[tag] = counts.get(tag, 0) + 1
    # Return average weight per tag
    return {tag: totals[tag] / counts[tag] for tag in totals}


# ── Tag clustering ─────────────────────────────────────────────────────────────

TAG_CLUSTERS: dict[str, list[str]] = {
    # ── Core 10 (original) ────────────────────────────────────────────────────
    "night":         ["night", "midnight", "late_night", "2am", "3am", "nocturnal",
                      "after_dark", "witching_hour", "insomnia"],
    "sad":           ["sad", "sadness", "crying", "hollow", "heartbreak", "sorrow",
                      "grief", "depressed", "numb", "empty", "melancholy", "hopeless",
                      "lyr_sad",                           # lyrics signal
                      # semantic_core alias resolution
                      "melancholic", "emotional", "lonely", "cathartic",
                      # bittersweet lives here (primary sad cluster; not in nostalgic)
                      "bittersweet"],
    "rage":          ["rage", "angry", "aggressive", "furious", "hate", "brutal",
                      "intense", "explosive", "bitter", "seething",
                      "lyr_angry",                         # lyrics signal
                      # semantic_core alias resolution
                      "chaotic", "menacing", "rebellious"],
    "calm":          ["calm", "peaceful", "tranquil", "serene", "gentle", "soft",
                      "soothing", "relax", "mellow", "ambient",
                      "sleep", "lullaby", "bedtime", "sleepy"],
    "hype":          ["hype", "energy", "energetic", "lit", "fire", "flames", "banger",
                      "pump", "electric", "amped", "turnt", "beast_mode",
                      # powerful lives in "confident" cluster (where it resolves correctly)
                      "lyr_hype",                          # lyrics signal
                      # semantic_core alias resolution
                      "celebratory", "anthemic", "marching", "epic", "gym",
                      # forbidden_tags dead-tag coverage
                      "trap", "workout", "gym_rage"],
    "dark":          ["dark", "darkness", "sinister", "gothic", "shadow", "noir",
                      "ominous", "haunting", "void", "abyss",
                      "lyr_dark",                          # lyrics signal
                      # semantic_core alias resolution
                      "cold", "anxious",
                      # forbidden_tags dead-tag coverage
                      "phonk", "phonk_only", "drill", "funeral", "scream", "death",
                      "doom", "death_metal"],
    "love":          ["love", "romance", "romantic", "lover", "crush", "adore",
                      "tender", "intimate", "heart",
                      "lyr_love",                          # lyrics signal
                      # semantic_core alias resolution
                      "sensual", "sexy"],
    "happy":         ["happy", "happiness", "joy", "bliss", "euphoria", "euphoric",
                      "elated", "cheerful", "upbeat", "smile",
                      # sunshine lives in "summer" cluster (where it resolves correctly)
                      "lyr_euphoric"],                     # lyrics signal
    "focus":         ["focus", "study", "concentrate", "productive", "flow",
                      "deep_work", "reading", "brain",
                      "lyr_introspective"],                # lyrics signal
    # "bittersweet" is in "sad" cluster (not here); resolves there correctly.
    "nostalgic":     ["nostalgia", "memories", "throwback", "vintage", "retro",
                      "classic", "childhood"],
    # ── Extended clusters (cover all semantic_core dims used in packs.json) ──
    "introspective": ["introspective", "reflective", "pensive", "contemplative",
                      "thoughtful", "meditation", "self_discovery", "searching",
                      "soul_searching", "inner", "vulnerable", "open",
                      # semantic_core alias resolution
                      "meditative", "devotional"],
    "party":         ["party", "parties", "celebration", "celebrate", "turn_up",
                      "club", "dance", "dancing", "dancefloor", "rave", "festival",
                      "anthem", "crowd", "vibe", "good_times", "pregame", "shots",
                      "lyr_party"],                        # lyrics signal
    "chill":         ["chill", "chilled", "chilling", "laid_back", "easy", "smooth",
                      "cozy", "slow", "sunset", "vibe", "vibes", "breezy", "slow_jams"],
    "angry":         ["angry", "anger", "mad", "pissed", "furious", "fury",
                      "frustrated", "frustration", "scorned", "revenge", "bitter",
                      "seething", "not_over_it"],
    "ambient":       ["ambient", "atmospheric", "ethereal", "cinematic", "spacey",
                      "texture", "soundscape", "dreamlike", "weightless", "drift",
                      "floating", "liminal", "eerie",
                      # semantic_core alias resolution
                      "hazy", "minimal", "subtle", "lush", "hypnotic", "nautical"],
    "drive":         ["drive", "driving", "road", "cruise", "highway", "car",
                      "journey", "travel", "open_road", "ride", "cruising",
                      "backroads", "freeway", "windows_down", "country_road"],
    "spiritual":     ["spiritual", "gospel", "sacred", "divine", "holy", "worship",
                      "prayer", "faith", "choir", "church", "blessed", "praise",
                      "revival", "anointed", "sanctified", "soulful", "transcendent",
                      # semantic_core alias resolution
                      "uplift", "hopeful"],
    "confident":     ["confident", "confidence", "boss", "winning", "winner",
                      "unstoppable", "invincible", "strong", "fearless", "bold",
                      "badass", "slay", "slaying", "queen", "king", "powerful"],
    "summer":        ["summer", "summertime", "beach", "sunshine", "warm", "warmth",
                      "tropical", "vacation", "holiday", "golden", "tan", "glow",
                      "pool", "hot", "waves", "outdoor"],
    "morning":       ["morning", "sunrise", "dawn", "wake", "waking", "early",
                      "fresh_start", "new_day", "coffee", "rise"],
    "groovy":        ["groove", "funky", "funk", "soul", "r&b", "rnb", "rhythmic",
                      "organic", "jazz", "smooth", "swing", "laid_back_groove"],
    "raw":           ["raw", "authentic", "real", "honest", "underground", "diy",
                      "lo_fi", "lofi", "acoustic", "stripped", "unfiltered",
                      # MB genre tags that map to raw/gritty energy
                      "gangsta", "gangsta_rap", "thug_rap", "punk", "punk_rock",
                      "punk-pop", "punk_revival", "alternative_punk",
                      # semantic_core alias resolution
                      "urban",
                      # forbidden_tag genre coverage (acoustic/folk styles)
                      "country", "bluegrass", "folk", "americana", "rap", "hip-hop"],
    "intense":       ["intense", "heavy", "brutal", "hardcore", "extreme",
                      "crushing", "pounding", "relentless", "ferocious",
                      # MB genre tags for heavy music
                      "alternative_rock", "hard_rock", "metal", "heavy_metal",
                      "post-hardcore",
                      # semantic_core alias resolution
                      "dramatic", "theatrical"],
    "electronic":    ["electronic", "edm", "synthwave", "techno", "house",
                      "trance", "beats", "808", "synth", "club_music",
                      "dj", "drop", "bass",
                      # MB genre tags for electronic subgenres
                      "synth-pop", "new_wave", "darkwave", "electropop",
                      "industrial", "ambient_electronic"],
    "mysterious":    ["mysterious", "mystery", "eerie", "haunted", "cryptic",
                      "uncanny", "surreal", "strange", "weird", "unsettling",
                      # semantic_core alias resolution
                      "trippy"],
    "vibrant":       ["vibrant", "colorful", "vivid", "lively", "playful", "bouncy",
                      "bubbly", "bright", "radiant", "sparkling"],
}

# Inverted lookup: tag → cluster name
_TAG_TO_CLUSTER: dict[str, str] = {
    tag: cluster
    for cluster, tags in TAG_CLUSTERS.items()
    for tag in tags
}


def collapse_tags(tags: dict[str, float]) -> dict[str, float]:
    """
    Collapse raw tag weights into semantic cluster weights.

    Rules (in order):
      1. Tag is a cluster member  → add to that cluster (max weight)
      2. Tag IS a cluster name    → pass through as-is (already canonical)
      3. Tag starts with "lyr_"  → pass through (lyrics signal, always keep)
      4. Otherwise               → discard

    Args:
        tags: {tag: weight} from track profile.

    Returns:
        {cluster_name: max_weight} for clusters with at least one hit,
        plus any lyr_* tags or direct cluster-name tags preserved.
    """
    clusters: dict[str, float] = {}
    for tag, weight in tags.items():
        # Rule 1: tag maps to a cluster via the inverted lookup
        cluster = _TAG_TO_CLUSTER.get(tag)
        if cluster:
            clusters[cluster] = max(clusters.get(cluster, 0.0), weight)
            continue
        # Rule 2: tag is already a cluster name (e.g. "hype" used directly)
        if tag in TAG_CLUSTERS:
            clusters[tag] = max(clusters.get(tag, 0.0), weight)
            continue
        # Rule 3: lyrics-derived signal — always preserve
        if tag.startswith("lyr_"):
            clusters[tag] = max(clusters.get(tag, 0.0), weight)
    return clusters
