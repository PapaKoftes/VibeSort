"""
audio_proxy.py — Metadata-only proxy for Spotify audio-features (deprecated).

Builds a Spotify-shaped feature dict from tags, genres, and Discogs-style keys
so profile.audio_vector and mood hard-filters can run without raw audio.
Not ground truth — heuristic only. See profile.audio_vector_source.
"""

from __future__ import annotations

from core.audio_groups import _GENRE_TEMPO, _STYLE_SUBSTRING_TEMPO
from core.genre import to_macro

_SOURCE = "metadata_proxy"

# Tempo band centres (BPM) → tempo_norm = min(bpm/200, 1.0)
_BAND_CENTER_BPM: dict[str, float] = {
    "Slow Burn":   78.0,
    "Cruise":     102.0,
    "Momentum":   125.0,
    "Rush":       147.0,
    "Hyperspeed": 172.0,
}


def _tag_blob(tags: dict[str, float]) -> str:
    parts = [k.lower() for k in tags if k and not str(k).lower().startswith("lyr_")]
    return " ".join(parts)


def _tempo_band_from_tags(tags: dict[str, float]) -> str | None:
    blob = _tag_blob(tags)
    if not blob.strip():
        return None
    for needle, band in _STYLE_SUBSTRING_TEMPO:
        if needle in blob:
            return band
    return None


def _tempo_band_from_macros(macros: list[str]) -> str:
    votes: dict[str, int] = {}
    for m in macros:
        b = _GENRE_TEMPO.get(m)
        if b:
            votes[b] = votes.get(b, 0) + 1
    if not votes:
        return "Momentum"
    return max(votes, key=lambda x: votes[x])


def _macro_genres_for_track(track: dict, artist_genres_map: dict[str, list[str]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for artist in track.get("artists", []) or []:
        aid = artist.get("id", "") if isinstance(artist, dict) else ""
        if not aid:
            continue
        for g in artist_genres_map.get(aid, []) or []:
            macro = to_macro(g)
            if macro not in seen:
                seen.add(macro)
                out.append(macro)
    return out or ["Other"]


def _heuristic_energy_valence_dance(tags: dict[str, float], lyric_mood: dict[str, float]) -> tuple[float, float, float]:
    """Return (energy, valence, danceability) in [0,1]."""
    blob = _tag_blob(tags)
    energy = 0.5
    valence = 0.5
    dance = 0.5

    high_e = ("hype", "rage", "party", "drill", "metal", "techno", "edm", "hardcore", "aggressive", "intense")
    low_e = ("calm", "ambient", "sleep", "slow", "acoustic", "soft", "chill", "peaceful")
    pos_v = ("happy", "love", "party", "summer", "euphoric", "confident", "celebration")
    neg_v = ("sad", "dark", "depressive", "grief", "hollow", "melancholy", "angry", "rage")
    dance_k = ("party", "dance", "club", "techno", "house", "disco", "funk", "reggaeton", "phonk")

    for kw in high_e:
        if kw in blob:
            energy = min(1.0, energy + 0.12)
    for kw in low_e:
        if kw in blob:
            energy = max(0.0, energy - 0.10)
    for kw in pos_v:
        if kw in blob:
            valence = min(1.0, valence + 0.10)
    for kw in neg_v:
        if kw in blob:
            valence = max(0.0, valence - 0.10)
    for kw in dance_k:
        if kw in blob:
            dance = min(1.0, dance + 0.14)

    if lyric_mood.get("sad", 0) > 0.2:
        valence = max(0.0, valence - 0.15 * min(lyric_mood["sad"], 1.0))
    if lyric_mood.get("euphoric", 0) > 0.2:
        valence = min(1.0, valence + 0.12 * min(lyric_mood["euphoric"], 1.0))
    if lyric_mood.get("hype", 0) > 0.2:
        energy = min(1.0, energy + 0.10 * min(lyric_mood["hype"], 1.0))
    if lyric_mood.get("dark", 0) > 0.2:
        valence = max(0.0, valence - 0.08 * min(lyric_mood["dark"], 1.0))

    return round(energy, 4), round(valence, 4), round(dance, 4)


def _heuristic_acoustic_instrumental(tags: dict[str, float], macros: list[str]) -> tuple[float, float]:
    blob = _tag_blob(tags)
    acoustic = 0.5
    instrumental = 0.0
    if any(x in blob for x in ("acoustic", "folk", "unplugged", "stripped", "piano", "guitar")):
        acoustic = 0.72
    if "ambient" in blob or "instrumental" in blob:
        instrumental = min(0.85, instrumental + 0.55)
    if any(m in ("Classical / Orchestral", "Ambient / Experimental", "Electronic / Ambient") for m in macros):
        if "Classical / Orchestral" in macros:
            instrumental = max(instrumental, 0.5)
        acoustic = max(acoustic, 0.45)
    return round(acoustic, 4), round(instrumental, 4)


def _proxy_confidence(tags: dict[str, float], macros: list[str]) -> float:
    n = 0.0
    if tags:
        n += min(1.0, len(tags) / 8.0) * 0.5
    if macros and macros != ["Other"]:
        n += 0.35
    if _tempo_band_from_tags(tags):
        n += 0.15
    return round(min(n, 1.0), 4)


def build_proxy_feature_dict(
    track: dict,
    artist_genres_map: dict[str, list[str]],
    track_tags: dict[str, dict[str, float]],
) -> dict | None:
    """
    Return a dict compatible with profile._audio_vector / scorer hard filters,
    or None if there is insufficient signal (caller keeps neutral sentinel).
    """
    uri = track.get("uri", "")
    if not uri:
        return None
    tags = track_tags.get(uri) or {}
    macros = _macro_genres_for_track(track, artist_genres_map)

    has_genre_signal = bool(macros) and macros != ["Other"]
    has_tag_signal = bool(tags)
    if not has_genre_signal and not has_tag_signal:
        return None

    band = _tempo_band_from_tags(tags) or _tempo_band_from_macros(macros)
    bpm = _BAND_CENTER_BPM.get(band, 120.0)

    lyric_mood = {
        k[4:]: v
        for k, v in tags.items()
        if isinstance(k, str) and k.startswith("lyr_")
    }
    energy, valence, dance = _heuristic_energy_valence_dance(tags, lyric_mood)
    acoustic, instrumental = _heuristic_acoustic_instrumental(tags, macros)

    return {
        "energy": energy,
        "valence": valence,
        "danceability": dance,
        "tempo": bpm,
        "acousticness": acoustic,
        "instrumentalness": instrumental,
        "_source": _SOURCE,
        "_proxy_confidence": _proxy_confidence(tags, macros),
        "_proxy_tempo_band": band,
    }


def merge_proxy_into_audio_map(
    all_tracks: list[dict],
    artist_genres_map: dict[str, list[str]],
    track_tags: dict[str, dict[str, float]],
    audio_features_map: dict[str, dict],
) -> int:
    """
    For each track without real Spotify audio features, attach metadata proxy
    when build_proxy_feature_dict returns data. Mutates audio_features_map.
    Returns count of tracks updated.
    """
    n = 0
    for t in all_tracks:
        uri = t.get("uri")
        if not uri:
            continue
        existing = audio_features_map.get(uri) or {}
        if _is_real_spotify_audio(existing):
            continue
        proxy = build_proxy_feature_dict(t, artist_genres_map, track_tags)
        if proxy:
            audio_features_map[uri] = proxy
            n += 1
    return n


def _is_real_spotify_audio(d: dict) -> bool:
    """True if this looks like a live Spotify audio-features payload."""
    if not d or d.get("_source") == _SOURCE:
        return False
    return any(d.get(k) is not None for k in ("energy", "valence", "danceability", "tempo", "acousticness"))
