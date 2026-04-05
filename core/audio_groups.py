"""
audio_groups.py — Group library tracks by audio characteristics.

Three grouping dimensions, each with a dual data path:
  1. Tempo / BPM     — uses tempo_norm (audio_vector[3]) when available;
                       falls back to macro_genre inference otherwise.
  2. Energy Level    — uses energy (audio_vector[0]) when available;
                       falls back to macro_genre inference.
  3. Sound Character — Acoustic / Instrumental / Electronic using
                       acousticness (index 4) + instrumentalness (index 5);
                       falls back to macro_genre inference.

"Real" audio features = Spotify audio-features endpoint was not 403'd.
Detection: if energy values across the library are all ~0.5 it's the
neutral default; genuine features have meaningful variance.
"""

from __future__ import annotations


# ─── Tempo / BPM bands ────────────────────────────────────────────────────────
# tempo_norm = Spotify tempo / 200  (covers the 60–200 BPM practical range)

TEMPO_BANDS: list[tuple[str, float, float, str]] = [
    # (label,         min_bpm, max_bpm, description)
    ("Slow Burn",        0,      90,   "Under 90 BPM — ambient, doom, slow jams, chopped & screwed"),
    ("Cruise",          90,     115,   "90–115 BPM — relaxed hip-hop, R&B, laid-back indie"),
    ("Momentum",       115,     135,   "115–135 BPM — standard pop/dance tempo, house, most rock"),
    ("Rush",           135,     160,   "135–160 BPM — hard techno, metal, uptempo EDM, punk"),
    ("Hyperspeed",     160,     999,   "160+ BPM — drum & bass, speed metal, breakcore, fast punk"),
]

# Macro genre → BPM band label (used as fallback when audio features absent)
_GENRE_TEMPO: dict[str, str] = {
    "Electronic / Drum & Bass":    "Hyperspeed",
    "Punk / Hardcore":             "Rush",
    "Emo / Post-Hardcore":         "Rush",
    "Metal":                       "Rush",
    "Electronic / Techno":         "Rush",
    "Electronic / Trance":         "Rush",
    "Hyperpop":                    "Rush",
    "Electronic / House":          "Momentum",
    "Electronic / Bass & Dubstep": "Momentum",
    "Phonk":                       "Momentum",
    "Brazilian Phonk":             "Momentum",
    "Pop":                         "Momentum",
    "Rock":                        "Momentum",
    "Classic Rock":                "Momentum",
    "K-Pop / J-Pop":               "Momentum",
    "Latin / Reggaeton":           "Momentum",
    "Afrobeats / Amapiano":        "Momentum",
    "Brazilian / Funk Carioca":    "Momentum",
    "Synthwave / Retrowave":       "Momentum",
    "Mexican Regional":            "Momentum",
    "East Coast Rap":              "Cruise",
    "West Coast Rap":              "Cruise",
    "Southern Rap":                "Cruise",
    "Midwest Rap":                 "Cruise",
    "UK Rap / Grime":              "Cruise",
    "French Rap":                  "Cruise",
    "R&B / Soul":                  "Cruise",
    "Indie / Alternative":         "Cruise",
    "Post-Punk / Darkwave":        "Cruise",
    "Country":                     "Cruise",
    "Jazz / Blues":                "Cruise",
    "Classical / Orchestral":      "Cruise",
    "Caribbean / Reggae":          "Cruise",
    "World / Regional":            "Cruise",
    "Houston Rap":                 "Slow Burn",    # chopped & screwed
    "Dark R&B":                    "Slow Burn",
    "Shoegaze / Dream Pop":        "Slow Burn",
    "Lo-Fi":                       "Slow Burn",
    "Electronic / Ambient":        "Slow Burn",
    "Ambient / Experimental":      "Slow Burn",
    "Folk / Americana":            "Slow Burn",
}

# Discogs-style / sub-genre substrings → tempo band (checked before macro-genre vote).
# Order: more specific phrases first.
_STYLE_SUBSTRING_TEMPO: list[tuple[str, str]] = [
    ("drum and bass", "Hyperspeed"),
    ("drum n bass", "Hyperspeed"),
    ("jungle", "Hyperspeed"),
    ("breakcore", "Hyperspeed"),
    ("speedcore", "Hyperspeed"),
    ("footwork", "Hyperspeed"),
    ("thrash", "Rush"),
    ("grindcore", "Rush"),
    ("hardcore techno", "Rush"),
    ("hard techno", "Rush"),
    ("gabber", "Rush"),
    ("speed metal", "Rush"),
    ("black metal", "Rush"),
    ("death metal", "Rush"),
    ("metalcore", "Rush"),
    ("hardcore punk", "Rush"),
    ("punk", "Rush"),
    ("techno", "Rush"),
    ("edm", "Rush"),
    ("big beat", "Rush"),
    ("doom metal", "Slow Burn"),
    ("funeral doom", "Slow Burn"),
    ("stoner rock", "Slow Burn"),
    ("stoner metal", "Slow Burn"),
    ("shoegaze", "Slow Burn"),
    ("slowcore", "Slow Burn"),
    ("dream pop", "Slow Burn"),
    ("ambient", "Slow Burn"),
    ("dark ambient", "Slow Burn"),
    ("drone", "Slow Burn"),
    ("cloud rap", "Cruise"),
    ("trap", "Cruise"),
    ("phonk", "Momentum"),
    ("house", "Momentum"),
    ("trance", "Rush"),
    ("uk garage", "Momentum"),
    ("synthwave", "Momentum"),
    ("boom bap", "Momentum"),
    ("conscious", "Cruise"),
    ("neo soul", "Cruise"),
    ("contemporary r&b", "Cruise"),
]


def _tempo_band_from_discogs_styles(tags: dict[str, float]) -> str | None:
    """Map Discogs-style tag names (non-lyr_*) to a tempo band, if any rule matches."""
    if not tags:
        return None
    blob = " ".join(
        k.lower()
        for k in tags
        if k and not str(k).lower().startswith("lyr_")
    )
    if not blob.strip():
        return None
    for needle, band in _STYLE_SUBSTRING_TEMPO:
        if needle in blob:
            return band
    return None


# ─── Energy bands ─────────────────────────────────────────────────────────────
# energy is audio_vector[0] — a 0–1 Spotify measure of intensity/activity

ENERGY_BANDS: list[tuple[str, float, float, str]] = [
    ("Downtempo",    0.0,  0.35,  "Low energy — ambient, acoustic, soft R&B, sleep music"),
    ("Mid Energy",   0.35, 0.65,  "Moderate energy — most rap, indie, casual listening"),
    ("Uptempo",      0.65, 0.85,  "High energy — dance, rock, pop, festival music"),
    ("High Energy",  0.85, 1.01,  "Maximum energy — metal, drum & bass, hard techno, hype"),
]

# Macro genre → energy band label (fallback)
_GENRE_ENERGY: dict[str, str] = {
    "Metal":                       "High Energy",
    "Punk / Hardcore":             "High Energy",
    "Electronic / Drum & Bass":    "High Energy",
    "Electronic / Techno":         "High Energy",
    "Hyperpop":                    "High Energy",
    "Emo / Post-Hardcore":         "Uptempo",
    "Electronic / Trance":         "Uptempo",
    "Electronic / House":          "Uptempo",
    "Electronic / Bass & Dubstep": "Uptempo",
    "Phonk":                       "Uptempo",
    "Brazilian Phonk":             "Uptempo",
    "Pop":                         "Uptempo",
    "Rock":                        "Uptempo",
    "Classic Rock":                "Uptempo",
    "K-Pop / J-Pop":               "Uptempo",
    "Latin / Reggaeton":           "Uptempo",
    "Afrobeats / Amapiano":        "Uptempo",
    "Brazilian / Funk Carioca":    "Uptempo",
    "Synthwave / Retrowave":       "Uptempo",
    "Mexican Regional":            "Uptempo",
    "East Coast Rap":              "Mid Energy",
    "West Coast Rap":              "Mid Energy",
    "Southern Rap":                "Mid Energy",
    "Houston Rap":                 "Mid Energy",
    "Midwest Rap":                 "Mid Energy",
    "UK Rap / Grime":              "Mid Energy",
    "French Rap":                  "Mid Energy",
    "R&B / Soul":                  "Mid Energy",
    "Indie / Alternative":         "Mid Energy",
    "Post-Punk / Darkwave":        "Mid Energy",
    "Country":                     "Mid Energy",
    "Jazz / Blues":                "Mid Energy",
    "Classical / Orchestral":      "Mid Energy",
    "Caribbean / Reggae":          "Mid Energy",
    "World / Regional":            "Mid Energy",
    "Dark R&B":                    "Downtempo",
    "Shoegaze / Dream Pop":        "Downtempo",
    "Lo-Fi":                       "Downtempo",
    "Electronic / Ambient":        "Downtempo",
    "Ambient / Experimental":      "Downtempo",
    "Folk / Americana":            "Downtempo",
}


# ─── Sound character ──────────────────────────────────────────────────────────
# acousticness = audio_vector[4],  instrumentalness = audio_vector[5]

CHARACTER_DEFS: list[tuple[str, str]] = [
    ("Acoustic",          "Organic sound — guitar, piano, room, unplugged feel"),
    ("Instrumental",      "No lead vocals — focus on arrangement or texture"),
    ("Electronic",        "Synthesised palette — drum machines, synths, digital production"),
    ("Vocal-Forward",       "Lead vocal carries the track — pop, R&B, ballad energy"),
    ("Heavy & Distorted",   "Weight and saturation — metal, punk, phonk, heavy bass"),
    ("Atmospheric & Wide",  "Space, reverb, slow builds — ambient, shoegaze, soundscapes"),
    ("Groove & Rhythm",     "Body-moving pocket — house, reggaeton, funk, afrobeats"),
]

# Thresholds for audio-feature mode
_ACOUSTIC_THRESHOLD     = 0.65   # acousticness ≥ this → Acoustic
_INSTRUMENTAL_THRESHOLD = 0.50   # instrumentalness ≥ this → Instrumental
_ELECTRONIC_THRESHOLD   = 0.15   # acousticness ≤ this → Electronic

# Macro genre → list of character labels (fallback; multi-label allowed)
_GENRE_CHARACTER: dict[str, list[str]] = {
    "Folk / Americana":            ["Acoustic", "Vocal-Forward"],
    "Country":                     ["Acoustic", "Vocal-Forward"],
    "Classical / Orchestral":      ["Acoustic", "Instrumental", "Atmospheric & Wide"],
    "Jazz / Blues":                ["Acoustic", "Instrumental", "Groove & Rhythm"],
    "Shoegaze / Dream Pop":        ["Acoustic", "Atmospheric & Wide"],
    "Ambient / Experimental":      ["Instrumental", "Atmospheric & Wide"],
    "Electronic / Ambient":        ["Instrumental", "Electronic", "Atmospheric & Wide"],
    "Electronic / Techno":         ["Instrumental", "Electronic", "Groove & Rhythm"],
    "Electronic / Drum & Bass":    ["Instrumental", "Electronic", "Heavy & Distorted", "Groove & Rhythm"],
    "Electronic / Trance":         ["Electronic", "Atmospheric & Wide"],
    "Electronic / House":          ["Electronic", "Groove & Rhythm"],
    "Electronic / Bass & Dubstep": ["Electronic", "Heavy & Distorted", "Groove & Rhythm"],
    "Synthwave / Retrowave":       ["Electronic", "Atmospheric & Wide"],
    "Lo-Fi":                       ["Electronic", "Atmospheric & Wide"],
    "Phonk":                       ["Electronic", "Heavy & Distorted"],
    "Brazilian Phonk":             ["Electronic", "Heavy & Distorted", "Groove & Rhythm"],
    "Hyperpop":                    ["Electronic", "Vocal-Forward", "Heavy & Distorted"],
    "Latin / Reggaeton":           ["Electronic", "Groove & Rhythm", "Vocal-Forward"],
    "K-Pop / J-Pop":               ["Electronic", "Vocal-Forward"],
    "Metal":                       ["Heavy & Distorted", "Vocal-Forward"],
    "Rock":                        ["Heavy & Distorted", "Vocal-Forward"],
    "Classic Rock":                ["Vocal-Forward", "Groove & Rhythm"],
    "Punk / Hardcore":            ["Heavy & Distorted", "Vocal-Forward"],
    "Emo / Post-Hardcore":         ["Heavy & Distorted", "Vocal-Forward", "Atmospheric & Wide"],
    "Post-Punk / Darkwave":        ["Atmospheric & Wide", "Electronic", "Vocal-Forward"],
    "Indie / Alternative":         ["Vocal-Forward", "Atmospheric & Wide"],
    "R&B / Soul":                  ["Vocal-Forward", "Groove & Rhythm"],
    "Dark R&B":                    ["Vocal-Forward", "Atmospheric & Wide", "Groove & Rhythm"],
    "Pop":                         ["Vocal-Forward", "Electronic"],
    "East Coast Rap":              ["Groove & Rhythm", "Vocal-Forward", "Heavy & Distorted"],
    "West Coast Rap":              ["Groove & Rhythm", "Vocal-Forward"],
    "Southern Rap":                ["Groove & Rhythm", "Vocal-Forward", "Heavy & Distorted"],
    "Houston Rap":                 ["Groove & Rhythm", "Vocal-Forward", "Atmospheric & Wide"],
    "Midwest Rap":                 ["Groove & Rhythm", "Vocal-Forward"],
    "UK Rap / Grime":              ["Heavy & Distorted", "Groove & Rhythm", "Vocal-Forward"],
    "French Rap":                  ["Groove & Rhythm", "Vocal-Forward"],
    "Caribbean / Reggae":          ["Groove & Rhythm", "Vocal-Forward"],
    "Afrobeats / Amapiano":        ["Groove & Rhythm", "Electronic", "Vocal-Forward"],
    "Mexican Regional":            ["Vocal-Forward", "Acoustic"],
    "World / Regional":            ["Vocal-Forward", "Acoustic", "Groove & Rhythm"],
}


# ─── Detection ────────────────────────────────────────────────────────────────

def has_real_audio(profiles: dict) -> bool:
    """
    Return True if audio_vector values vary enough to use vector[3] as tempo_norm
    (Spotify API features and/or metadata proxy — not the flat neutral sentinel).
    """
    if not profiles:
        return False
    sample = list(profiles.values())[:200]
    energies = [p.get("audio_vector", [0.5] * 6)[0] for p in sample]
    unique = len(set(round(e, 2) for e in energies))
    return unique > 5


# ─── Grouping helpers ─────────────────────────────────────────────────────────

def _assign_band_by_genre(
    macros: list[str],
    genre_map: dict[str, str],
    default: str,
) -> str:
    """Vote-based: assign to whichever band gets the most genre-votes."""
    votes: dict[str, int] = {}
    for macro in macros:
        band = genre_map.get(macro)
        if band:
            votes[band] = votes.get(band, 0) + 1
    return max(votes, key=lambda b: votes[b]) if votes else default


# ─── Public API ───────────────────────────────────────────────────────────────

def tempo_groups(
    profiles: dict,
    min_tracks: int = 5,
) -> dict[str, dict]:
    """
    Group tracks by BPM / tempo band.

    Returns:
        {band_label: {"uris": [...], "bpm_range": str, "description": str,
                      "source": "audio_features" | "genre_inference"}}
    """
    use_audio = has_real_audio(profiles)
    groups: dict[str, list[str]] = {label: [] for label, *_ in TEMPO_BANDS}
    style_hits = 0

    for uri, profile in profiles.items():
        av     = profile.get("audio_vector", [0.5] * 6)
        macros = profile.get("macro_genres", ["Other"])
        tags   = profile.get("tags") or {}

        if use_audio:
            bpm = av[3] * 200.0
            assigned = False
            for label, lo, hi, _ in TEMPO_BANDS:
                if lo <= bpm < hi:
                    groups[label].append(uri)
                    assigned = True
                    break
            if not assigned:
                groups["Slow Burn"].append(uri)
        else:
            style_band = _tempo_band_from_discogs_styles(tags)
            if style_band:
                band = style_band
                style_hits += 1
            else:
                band = _assign_band_by_genre(macros, _GENRE_TEMPO, "Cruise")
            groups[band].append(uri)

    if use_audio:
        source = "audio_features"
    elif style_hits:
        source = "genre_and_style_inference"
    else:
        source = "genre_inference"
    result: dict[str, dict] = {}
    for label, lo, hi, description in TEMPO_BANDS:
        uris = list(dict.fromkeys(groups[label]))
        if len(uris) < min_tracks:
            continue
        if lo == 0:
            bpm_range = f"< {int(hi)} BPM"
        elif hi >= 999:
            bpm_range = f"{int(lo)}+ BPM"
        else:
            bpm_range = f"{int(lo)}–{int(hi)} BPM"
        result[label] = {
            "uris":        uris,
            "bpm_range":   bpm_range,
            "description": description,
            "source":      source,
        }
    return result


def energy_groups(
    profiles: dict,
    min_tracks: int = 5,
) -> dict[str, dict]:
    """
    Group tracks by energy level (Downtempo → High Energy).

    Returns:
        {band_label: {"uris": [...], "range": str, "description": str,
                      "source": "audio_features" | "genre_inference"}}
    """
    use_audio = has_real_audio(profiles)
    groups: dict[str, list[str]] = {label: [] for label, *_ in ENERGY_BANDS}

    for uri, profile in profiles.items():
        av     = profile.get("audio_vector", [0.5] * 6)
        macros = profile.get("macro_genres", ["Other"])

        if use_audio:
            energy   = av[0]
            assigned = False
            for label, lo, hi, _ in ENERGY_BANDS:
                if lo <= energy < hi:
                    groups[label].append(uri)
                    assigned = True
                    break
            if not assigned:
                groups["Mid Energy"].append(uri)
        else:
            band = _assign_band_by_genre(macros, _GENRE_ENERGY, "Mid Energy")
            groups[band].append(uri)

    source = "audio_features" if use_audio else "genre_inference"
    result: dict[str, dict] = {}
    for label, lo, hi, description in ENERGY_BANDS:
        uris = list(dict.fromkeys(groups[label]))
        if len(uris) < min_tracks:
            continue
        result[label] = {
            "uris":        uris,
            "range":       f"{int(lo * 100)}–{int(hi * 100)}%" if hi < 1.0 else f"{int(lo * 100)}%+",
            "description": description,
            "source":      source,
        }
    return result


def character_groups(
    profiles: dict,
    min_tracks: int = 5,
) -> dict[str, dict]:
    """
    Group tracks by sound character (timbre / role / production).
    A track can appear in multiple groups.

    Returns:
        {char_label: {"uris": [...], "description": str,
                      "source": "audio_features" | "genre_inference"}}
    """
    use_audio = has_real_audio(profiles)
    groups: dict[str, list[str]] = {label: [] for label, _ in CHARACTER_DEFS}

    for uri, profile in profiles.items():
        av     = profile.get("audio_vector", [0.5] * 6)
        macros = [m for m in profile.get("macro_genres", ["Other"]) if m != "Other"]
        if not macros:
            macros = ["Other"]

        if use_audio:
            acousticness     = av[4]
            instrumentalness = av[5]
            energy           = av[0]
            valence          = av[1]
            if acousticness >= _ACOUSTIC_THRESHOLD:
                groups["Acoustic"].append(uri)
            if instrumentalness >= _INSTRUMENTAL_THRESHOLD:
                groups["Instrumental"].append(uri)
            if acousticness <= _ELECTRONIC_THRESHOLD:
                groups["Electronic"].append(uri)
            if instrumentalness < 0.22 and acousticness < 0.55:
                groups["Vocal-Forward"].append(uri)
            if energy >= 0.62 and valence <= 0.42:
                groups["Heavy & Distorted"].append(uri)
            if energy <= 0.48 and (instrumentalness >= 0.2 or acousticness >= 0.35):
                groups["Atmospheric & Wide"].append(uri)
            if av[2] >= 0.58 and energy >= 0.45:
                groups["Groove & Rhythm"].append(uri)
        else:
            inferred: set[str] = set()
            for macro in macros:
                for char in _GENRE_CHARACTER.get(macro, []):
                    inferred.add(char)
            if not inferred and macros == ["Other"]:
                inferred.add("Vocal-Forward")
            for char in inferred:
                if char in groups:
                    groups[char].append(uri)

    source = "audio_features" if use_audio else "genre_inference"
    result: dict[str, dict] = {}
    for label, description in CHARACTER_DEFS:
        uris = list(dict.fromkeys(groups[label]))
        if len(uris) < min_tracks:
            continue
        result[label] = {
            "uris":        uris,
            "description": description,
            "source":      source,
        }
    return result
