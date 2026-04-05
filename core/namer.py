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


def _dominant_artist(track_profiles: list[dict], threshold: float = 0.45) -> str | None:
    """
    Return the most-played artist name if they account for >= threshold of tracks.
    Returns None if no single artist dominates.
    """
    if not track_profiles:
        return None
    counts: dict[str, int] = collections.Counter()
    for p in track_profiles:
        artists = p.get("artists", [])
        if artists:
            counts[artists[0]] += 1   # credit primary artist only
    if not counts:
        return None
    top_artist, top_count = counts.most_common(1)[0]
    if top_count / len(track_profiles) >= threshold:
        return top_artist
    return None


def _artist_playlist_name(artist_name: str) -> str:
    """
    Format an artist name for the "Your ___" style.
    Strips leading 'The ' so "The 1975" → "Your 1975",
    "The Beatles" → "Your Beatles", "Drake" → "Your Drake".
    """
    name = artist_name.strip()
    if name.lower().startswith("the "):
        name = name[4:]
    return f"Your {name}"


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
    # Exclude "Other" so that a library with no genre data doesn't produce a
    # playlist named "Other" — fall through to descriptor-based naming instead.
    top_genres = [g for g in list(summary.keys())[:2] if g != "Other"]
    track_count = len(track_profiles)

    audio_mean = _audio_mean_from_profiles(track_profiles)
    descriptor = energy_descriptor(audio_mean)
    profile_tags = _top_profile_tags(track_profiles, n=3)
    char_str = " · ".join(profile_tags) if profile_tags else descriptor

    # Single-artist dominance → "Your [Artist]"
    dominant = _dominant_artist(track_profiles, threshold=0.45)
    if dominant:
        playlist_name = _artist_playlist_name(dominant)
        genre_str = " / ".join(_shorten_genre(g) for g in top_genres) if top_genres else ""
        genre_part = f" {genre_str}." if genre_str else "."
        desc = f"{track_count} tracks — your {dominant} picks.{genre_part} {char_str}."
        lyric_line = _lyric_sentence_for_description(track_profiles)
        if lyric_line:
            desc = f"{lyric_line} {desc}"
        return (playlist_name, desc)

    lyric_lead = _lyric_phrase_for_name(None, track_profiles)

    # Build name
    if not top_genres:
        name = lyric_lead if lyric_lead else (profile_tags[0] if profile_tags else "Mixed")
    elif len(top_genres) == 1:
        name = f"{lyric_lead} — {top_genres[0]}" if lyric_lead else top_genres[0]
    else:
        top_pct = summary[top_genres[0]]["percentage"]
        if top_pct >= 0.70:
            base = top_genres[0]
        else:
            g1, g2 = top_genres[0], top_genres[1]
            short1 = _shorten_genre(g1)
            short2 = _shorten_genre(g2)
            base = f"{short1} / {short2}"
        name = f"{lyric_lead} — {base}" if lyric_lead else base

    # Build description — mood character first, genre breakdown second
    genre_parts = []
    for g, info in list(summary.items())[:3]:
        if g == "Other":
            continue
        pct = int(info["percentage"] * 100)
        genre_parts.append(f"{g} ({pct}%)")

    genre_str = ", ".join(genre_parts) if genre_parts else None
    if genre_str:
        description = f"{track_count} tracks — {char_str}. {genre_str}."
    else:
        description = f"{track_count} tracks — {char_str}."
    lyric_line = _lyric_sentence_for_description(track_profiles)
    if lyric_line:
        description = f"{lyric_line} {description}"

    return (name, description)


def _clean_tag_label(tag: str) -> str:
    return tag.replace("_", " ").strip().title()


def _top_observed_tag(observed_tags: dict[str, float] | None) -> str | None:
    if not observed_tags:
        return None
    top = sorted(observed_tags.items(), key=lambda x: -x[1])[0][0]
    return _clean_tag_label(top)


# Tags that add no descriptive value in playlist descriptions
_DESC_SKIP_TAGS: frozenset = frozenset({
    "other", "music", "song", "track", "unknown", "various", "mix",
    "playlist", "hits", "top", "best", "favorite", "favourite", "all",
    "lyr_sad", "lyr_dark", "lyr_love", "lyr_hype", "lyr_introspective",
    "lyr_euphoric", "lyr_party", "lyr_angry",
})

# Human-readable lyric themes for playlist titles / descriptions (keys = lyric_mood labels, no lyr_ prefix)
_LYRIC_THEME_LABELS: dict[str, str] = {
    "sad": "Sad lyrics",
    "angry": "Angry lyrics",
    "love": "Love songs",
    "hype": "Hype bars",
    "introspective": "Introspective lyrics",
    "euphoric": "Euphoric lyrics",
    "dark": "Dark lyrics",
    "party": "Party lyrics",
    "goodbye": "Goodbyes & leaving",
    "homesick": "Home & roots",
    "nostalgic": "Nostalgia",
    "hope": "Hope & keeping on",
    "struggle": "Struggle & grind",
    "faith": "Faith & spirit",
    "missing_you": "Missing someone",
    "revenge": "Revenge & payback",
    "money": "Money & flex",
    "freedom": "Freedom & escape",
    "night_drive": "Late-night stories",
    "family": "Family & kin",
    "friends": "Crew & loyalty",
    "jealousy": "Jealousy & tension",
    "summer": "Summer energy",
    "city": "City life",
    "ocean": "Sea & escape",
}


def _aggregate_lyric_moods(track_profiles: list[dict]) -> list[tuple[str, float]]:
    """Mean lyr_* signal strength per theme across tracks (lyric_mood keys, no lyr_ prefix)."""
    if not track_profiles:
        return []
    agg: dict[str, float] = collections.defaultdict(float)
    for p in track_profiles:
        lm = p.get("lyric_mood") or {}
        for k, v in lm.items():
            agg[k] += float(v or 0.0)
    n = len(track_profiles)
    out = [(k, agg[k] / n) for k in agg]
    out.sort(key=lambda x: -x[1])
    return out


def _lyric_phrase_for_name(mood_name: str | None, track_profiles: list[dict]) -> str | None:
    """
    Short phrase to put in the playlist title when lyrics carry the vibe.
    Uses pack.lyric_playlist_title if set; else dominant aggregated lyric themes.
    """
    from core.mood_graph import get_mood, mood_lyric_focus

    pack = get_mood(mood_name) if mood_name else None
    if pack:
        hint = (pack.get("lyric_playlist_title") or "").strip()
        if hint:
            return hint
    ranked = _aggregate_lyric_moods(track_profiles)
    if not ranked:
        return None
    top_w = ranked[0][1]
    need = 0.07 if (mood_name and mood_lyric_focus(mood_name)) else 0.11
    if top_w < need:
        return None
    labels: list[str] = []
    for key, w in ranked[:2]:
        if w < need * 0.55:
            break
        labels.append(_LYRIC_THEME_LABELS.get(key, key.replace("_", " ").title()))
    if not labels:
        return None
    return " & ".join(labels)


def _lyric_sentence_for_description(track_profiles: list[dict]) -> str | None:
    """One line for playlist description summarising lyric consensus."""
    ranked = _aggregate_lyric_moods(track_profiles)
    if not ranked or ranked[0][1] < 0.06:
        return None
    parts: list[str] = []
    for key, w in ranked[:3]:
        if w < 0.045:
            break
        parts.append(_LYRIC_THEME_LABELS.get(key, key.replace("_", " ").title()).lower())
    if not parts:
        return None
    return "Lyrics across these tracks lean toward: " + ", ".join(parts) + "."


def _base_playlist_name(mood_name: str) -> str:
    from core.mood_graph import mood_display_name

    return mood_display_name(mood_name)


def _top_profile_tags(track_profiles: list[dict], n: int = 3) -> list[str]:
    """
    Aggregate the most characteristic mood/feel tags across track profiles.

    Prefers tag_clusters (canonical cluster names) over raw tags.
    Skips generic filler and lyr_* tags (which are internal signals, not labels).
    Returns up to n cleaned, human-readable tag labels.
    """
    counts: dict[str, float] = collections.Counter()
    for p in track_profiles:
        clusters = p.get("tag_clusters") or {}
        raw_tags = p.get("tags") or {}
        # tag_clusters are canonical and compact — prefer them
        combined = {**raw_tags, **clusters}
        for tag, weight in combined.items():
            t = tag.lower().strip()
            if t in _DESC_SKIP_TAGS or t.startswith("lyr_"):
                continue
            # Skip pure genre tags — those go in the genre section of the description
            if t in {
                "hip_hop", "rap", "rnb", "r&b", "electronic", "pop", "rock",
                "metal", "jazz", "classical", "country", "latin", "reggae",
                "folk", "soul", "funk", "blues", "ambient", "house", "techno",
                "trance", "drum_and_bass", "dnb", "dubstep", "afrobeats",
                "k_pop", "j_pop", "indie", "alternative", "punk", "emo",
            }:
                continue
            counts[t] += float(weight or 0.5)

    top = sorted(counts.items(), key=lambda x: -x[1])[:n]
    return [_clean_tag_label(t) for t, _ in top]


def top_down_name(
    mood_name: str,
    track_profiles: list[dict],
    observed_tags: dict[str, float] | None = None,
) -> tuple[str, str]:
    """
    Generate a playlist name and description using a preset mood name.

    - Playlist title uses mood display name; when lyrics match the pack, leads with a
      lyric theme phrase (e.g. "Goodbyes & leaving — Goodbye Songs").
    - Description opens with a lyric-consensus line when lyr_* data is present.

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
    summary = genre_summary(track_profiles)
    top_genres = [g for g in list(summary.keys())[:2] if g != "Other"]
    genre_str = " / ".join(_shorten_genre(g) for g in top_genres) if top_genres else None

    profile_tags = _top_profile_tags(track_profiles, n=3)
    obs = _top_observed_tag(observed_tags)
    if obs and obs.lower() not in [t.lower() for t in profile_tags]:
        profile_tags.append(obs)
    profile_tags = profile_tags[:3]

    char_str = " · ".join(profile_tags) if profile_tags else energy_descriptor(
        _audio_mean_from_profiles(track_profiles)
    )

    lyric_line = _lyric_sentence_for_description(track_profiles)
    if genre_str:
        description = f"{pack_desc}. {track_count} tracks — {char_str}. {genre_str}."
    else:
        description = f"{pack_desc}. {track_count} tracks — {char_str}."
    if lyric_line:
        description = f"{lyric_line} {description}"

    base = _base_playlist_name(mood_name)
    lyric_lead = _lyric_phrase_for_name(mood_name, track_profiles)
    if lyric_lead:
        playlist_name = f"{lyric_lead} — {base}"
    else:
        playlist_name = base

    return (playlist_name, description)


def middle_out_name(
    track_profiles: list[dict],
    mood_name: Optional[str] = None,
    observed_tags: dict[str, float] | None = None,
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
    # Exclude "Other" from top_genres — it's a fallback bucket, not a real genre label.
    # Without this filter a library with zero genre data would return ("Other", ...) from
    # Decision 1 (100% "Other" ≥ 0.60), bypassing the mood-name and hybrid decisions.
    top_genres = [g for g in list(summary.keys()) if g != "Other"]
    track_count = len(track_profiles)
    audio_mean = _audio_mean_from_profiles(track_profiles)
    descriptor = energy_descriptor(audio_mean)

    # Decision 0: Single-artist dominance → "Your [Artist]" only when no mood
    # context was explicitly requested.
    dominant = _dominant_artist(track_profiles, threshold=0.45)
    if dominant and not mood_name:
        playlist_name = _artist_playlist_name(dominant)
        genre_str = " / ".join(_shorten_genre(g) for g in top_genres[:2]) if top_genres else "Various"
        desc = f"{track_count} tracks — your {dominant} picks. {genre_str}. {descriptor}."
        return (playlist_name, desc)

    # Decision 1: If mood_name is provided, keep mood identity and enrich description
    # with observed pattern tags from the user's own library contexts.
    if mood_name:
        return top_down_name(mood_name, track_profiles, observed_tags=observed_tags)

    # Decision 2: Strong single-genre dominance (only fires when real genres are present)
    if top_genres and summary[top_genres[0]]["percentage"] >= 0.60:
        dominant = top_genres[0]
        second = top_genres[1] if len(top_genres) > 1 else None
        second_str = f", {_shorten_genre(second)}" if second else ""
        desc = (
            f"{track_count} tracks — {dominant}{second_str}. "
            f"{descriptor}."
        )
        return (dominant, desc)

    # Decision 3: Hybrid name — use mood tags to build a character label
    profile_tags = _top_profile_tags(track_profiles, n=3)
    char_str = " · ".join(profile_tags) if profile_tags else descriptor

    if top_genres:
        short_genre = _shorten_genre(top_genres[0])
        # If we have mood tags, name the playlist by top tag + genre for specificity
        if profile_tags:
            hybrid_name = f"{profile_tags[0]} {short_genre}".strip()
        else:
            hybrid_name = f"{descriptor} {short_genre}".strip()
    else:
        # No genre data — prefer mood name, then top tag, then descriptor
        if mood_name:
            hybrid_name = mood_name
        elif profile_tags:
            hybrid_name = profile_tags[0]
        else:
            hybrid_name = f"{descriptor} Mix"

    genre_parts = [_shorten_genre(g) for g in top_genres[:3]]
    genre_str = " / ".join(genre_parts) if genre_parts else None

    if genre_str:
        description = f"{track_count} tracks — {char_str}. {genre_str}."
    else:
        description = f"{track_count} tracks — {char_str}."
    lyric_line = _lyric_sentence_for_description(track_profiles)
    if lyric_line:
        description = f"{lyric_line} {description}"

    lyric_lead = _lyric_phrase_for_name(None, track_profiles)
    if lyric_lead and hybrid_name and lyric_lead.lower() not in hybrid_name.lower():
        hybrid_name = f"{lyric_lead} — {hybrid_name}"

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
