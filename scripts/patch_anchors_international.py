#!/usr/bin/env python3
"""
patch_anchors_international.py
Adds comprehensive international anchor tracks to mood_anchors.json.
Covers: Arabic/MENA, French rap, German rap, Brazilian funk/phonk,
Turkish rap/pop, Hindi/Bollywood, Spanish-language rock, Italian trap/pop,
Russian rap.
Idempotent: re-running adds 0 duplicates.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

ANCHORS_PATH = Path("C:/Github/PapaKoftes/Vibesort/data/mood_anchors.json")

# ---------------------------------------------------------------------------
# Build additions as a list of (mood, artist, title) tuples to avoid
# the Python dict duplicate-key overwrite problem.
# ---------------------------------------------------------------------------

def T(mood, artist, title):
    return (mood, artist, title)

ADDITIONS = [

    # ===================================================================
    # ARABIC / MENA
    # ===================================================================

    # Hollow / introspective / late-night darkness
    T("Hollow",             "Shabjdeed",    "وش في وش"),
    T("Hollow",             "Al Nather",    "حالة صعبة"),
    T("Hollow",             "Abyusif",      "يا بختك"),
    T("Hollow",             "El Rass",      "كل شي ممكن"),
    T("Hollow",             "Lege-Cy",      "مش قادر"),

    T("Rainy Window",       "Shabjdeed",    "وش في وش"),
    T("Rainy Window",       "Al Nather",    "ليه"),
    T("Rainy Window",       "Lege-Cy",      "مش قادر"),
    T("Rainy Window",       "Abyusif",      "الراحة"),

    T("3 AM Unsent Texts",  "Lege-Cy",      "مش قادر"),
    T("3 AM Unsent Texts",  "Al Nather",    "ليه"),
    T("3 AM Unsent Texts",  "Shabjdeed",    "بدي ارتاح"),

    T("Overthinking",       "Al Nather",    "حالة صعبة"),
    T("Overthinking",       "El Rass",      "كل شي ممكن"),
    T("Overthinking",       "Shabjdeed",    "بدي ارتاح"),

    # Villain Arc / hype / trap
    T("Villain Arc",        "Wegz",         "El Bakht"),
    T("Villain Arc",        "Marwan Pablo", "Emotions"),
    T("Villain Arc",        "Abyusif",      "بطل"),
    T("Villain Arc",        "Shabjdeed",    "كوكب الشر"),
    T("Villain Arc",        "El Rass",      "Nefsy"),

    T("Adrenaline",         "Wegz",         "El Bakht"),
    T("Adrenaline",         "Marwan Pablo", "Emotions"),
    T("Adrenaline",         "Abyusif",      "بطل"),
    T("Adrenaline",         "Lege-Cy",      "Nightmare"),

    T("Rage Lift",          "Marwan Pablo", "Emotions"),
    T("Rage Lift",          "Wegz",         "El Bakht"),
    T("Rage Lift",          "Abyusif",      "بطل"),
    T("Rage Lift",          "El Rass",      "Nefsy"),

    T("Hard Reset",         "Wegz",         "El Bakht"),
    T("Hard Reset",         "Marwan Pablo", "Emotions"),
    T("Hard Reset",         "Abyusif",      "بطل"),

    # Late Night Drive / nocturnal
    T("Late Night Drive",   "Abyusif",      "Cairo"),
    T("Late Night Drive",   "Marwan Pablo", "Paranoia"),
    T("Late Night Drive",   "Shabjdeed",    "بدي ارتاح"),
    T("Late Night Drive",   "Wegz",         "Mesh Btetkhayyal"),

    T("Smoke & Mirrors",    "Abyusif",      "Cairo"),
    T("Smoke & Mirrors",    "Marwan Pablo", "Paranoia"),
    T("Smoke & Mirrors",    "Shabjdeed",    "كوكب الشر"),

    # Money / Flex
    T("Money Talks",        "Wegz",         "El Bakht"),
    T("Money Talks",        "Marwan Pablo", "Emotions"),
    T("Money Talks",        "Abyusif",      "بطل"),
    T("Money Talks",        "Shabjdeed",    "كوكب الشر"),

    T("Flex Tape",          "Wegz",         "El Bakht"),
    T("Flex Tape",          "Marwan Pablo", "Emotions"),
    T("Flex Tape",          "Abyusif",      "بطل"),

    # ===================================================================
    # FRENCH RAP
    # ===================================================================

    T("Hollow",             "Nekfeu",           "La fuite en avant"),
    T("Hollow",             "Lomepal",          "Trop beau"),
    T("Hollow",             "Hamza",            "Merci"),
    T("Hollow",             "Laylow",           "Trinity"),
    T("Hollow",             "Damso",            "Macarena"),

    T("Rainy Window",       "Nekfeu",           "La fuite en avant"),
    T("Rainy Window",       "Lomepal",          "Trop beau"),
    T("Rainy Window",       "Damso",            "Ipséité"),
    T("Rainy Window",       "Laylow",           "Déjà loin"),

    T("3 AM Unsent Texts",  "Nekfeu",           "La fuite en avant"),
    T("3 AM Unsent Texts",  "Lomepal",          "Trop beau"),
    T("3 AM Unsent Texts",  "Laylow",           "Déjà loin"),

    T("Overthinking",       "Nekfeu",           "La fuite en avant"),
    T("Overthinking",       "Damso",            "Ipséité"),
    T("Overthinking",       "Lomepal",          "Trop beau"),
    T("Overthinking",       "Laylow",           "Trinity"),

    # Villain Arc / hard rap
    T("Villain Arc",        "Freeze Corleone",  "LMF"),
    T("Villain Arc",        "SCH",              "JVLIVS"),
    T("Villain Arc",        "Gazo",             "Drill FR"),
    T("Villain Arc",        "Ninho",            "Millions"),

    T("Adrenaline",         "Freeze Corleone",  "LMF"),
    T("Adrenaline",         "SCH",              "JVLIVS"),
    T("Adrenaline",         "Gazo",             "Drill FR"),
    T("Adrenaline",         "Ninho",            "Millions"),

    T("Rage Lift",          "Freeze Corleone",  "LMF"),
    T("Rage Lift",          "SCH",              "JVLIVS"),
    T("Rage Lift",          "Gazo",             "Drill FR"),

    T("Hard Reset",         "SCH",              "JVLIVS"),
    T("Hard Reset",         "Freeze Corleone",  "LMF"),
    T("Hard Reset",         "Gazo",             "Drill FR"),

    # Late Night / atmospheric
    T("Late Night Drive",   "Hamza",            "Sapés comme jamais"),
    T("Late Night Drive",   "Laylow",           "Trinity"),
    T("Late Night Drive",   "Nekfeu",           "Etoiles"),
    T("Late Night Drive",   "Lomepal",          "Trop beau"),

    T("Smoke & Mirrors",    "Hamza",            "Sapés comme jamais"),
    T("Smoke & Mirrors",    "Laylow",           "Trinity"),
    T("Smoke & Mirrors",    "Nekfeu",           "Etoiles"),

    # Deep Focus / lo-fi
    T("Deep Focus",         "Nekfeu",           "La fuite en avant"),
    T("Deep Focus",         "Laylow",           "Trinity"),
    T("Deep Focus",         "Lomepal",          "Trop beau"),

    T("Work Mode",          "Laylow",           "Trinity"),
    T("Work Mode",          "Nekfeu",           "Etoiles"),
    T("Work Mode",          "Hamza",            "Sapés comme jamais"),

    # Money / flex
    T("Money Talks",        "Ninho",            "Millions"),
    T("Money Talks",        "SCH",              "JVLIVS"),
    T("Money Talks",        "Gazo",             "Drill FR"),

    T("Flex Tape",          "Ninho",            "Millions"),
    T("Flex Tape",          "SCH",              "JVLIVS"),

    # ===================================================================
    # GERMAN RAP
    # ===================================================================

    T("Villain Arc",        "Capital Bra",      "Neymar"),
    T("Villain Arc",        "Ufo361",           "Habibi"),
    T("Villain Arc",        "Bonez MC",         "Palmen aus Plastik"),
    T("Villain Arc",        "Loredana",         "Ferrari"),
    T("Villain Arc",        "Pashanim",         "Zuhause"),

    T("Adrenaline",         "Capital Bra",      "Neymar"),
    T("Adrenaline",         "Ufo361",           "Habibi"),
    T("Adrenaline",         "Bonez MC",         "Palmen aus Plastik"),

    T("Hard Reset",         "Capital Bra",      "Neymar"),
    T("Hard Reset",         "Ufo361",           "Habibi"),
    T("Hard Reset",         "Bonez MC",         "Palmen aus Plastik"),

    T("Money Talks",        "Capital Bra",      "Neymar"),
    T("Money Talks",        "Ufo361",           "Habibi"),
    T("Money Talks",        "Loredana",         "Ferrari"),

    T("Flex Tape",          "Capital Bra",      "Neymar"),
    T("Flex Tape",          "Loredana",         "Ferrari"),
    T("Flex Tape",          "Ufo361",           "Habibi"),

    T("Late Night Drive",   "Rin",              "Blackout"),
    T("Late Night Drive",   "Pashanim",         "Zuhause"),
    T("Late Night Drive",   "Apache 207",       "Roller"),

    T("Smoke & Mirrors",    "Rin",              "Blackout"),
    T("Smoke & Mirrors",    "Apache 207",       "Roller"),
    T("Smoke & Mirrors",    "Pashanim",         "Zuhause"),

    T("Rainy Window",       "Pashanim",         "Zuhause"),
    T("Rainy Window",       "Rin",              "Blackout"),
    T("Rainy Window",       "Apache 207",       "Bläulich"),

    T("Hollow",             "Pashanim",         "Zuhause"),
    T("Hollow",             "Rin",              "Blackout"),

    # ===================================================================
    # BRAZILIAN FUNK / PHONK
    # ===================================================================

    T("Phonk Season",       "MC Ryan SP",       "Não Existe Amor em SP"),
    T("Phonk Season",       "Poze do Rodo",     "Não É Céu"),
    T("Phonk Season",       "Oruam",            "Cangaceiro"),
    T("Phonk Season",       "Menor Nico",       "Ainda Bem"),
    T("Phonk Season",       "MC Cabelinho",     "Beijo de Mel"),
    T("Phonk Season",       "MC Hariel",        "Ela É do Tipo"),

    T("Hard Reset",         "MC Ryan SP",       "Não Existe Amor em SP"),
    T("Hard Reset",         "Poze do Rodo",     "Não É Céu"),
    T("Hard Reset",         "Oruam",            "Cangaceiro"),
    T("Hard Reset",         "MC Cabelinho",     "Beijo de Mel"),

    T("Adrenaline",         "Poze do Rodo",     "Não É Céu"),
    T("Adrenaline",         "Oruam",            "Cangaceiro"),
    T("Adrenaline",         "MC Ryan SP",       "Não Existe Amor em SP"),

    T("Late Night Drive",   "Menor Nico",       "Ainda Bem"),
    T("Late Night Drive",   "MC Ryan SP",       "Não Existe Amor em SP"),
    T("Late Night Drive",   "Poze do Rodo",     "Não É Céu"),

    T("Afterparty",         "MC Hariel",        "Ela É do Tipo"),
    T("Afterparty",         "MC Cabelinho",     "Beijo de Mel"),
    T("Afterparty",         "Oruam",            "Cangaceiro"),
    T("Afterparty",         "Poze do Rodo",     "Não É Céu"),

    T("Latin Heat",         "MC Hariel",        "Ela É do Tipo"),
    T("Latin Heat",         "MC Cabelinho",     "Beijo de Mel"),
    T("Latin Heat",         "Oruam",            "Cangaceiro"),
    T("Latin Heat",         "Menor Nico",       "Ainda Bem"),

    # ===================================================================
    # TURKISH RAP / POP
    # ===================================================================

    T("Villain Arc",        "Ceza",             "Holocaust"),
    T("Villain Arc",        "UZI",              "Kahraman Olamam"),
    T("Villain Arc",        "Ben Fero",         "Dibine Kadar"),
    T("Villain Arc",        "Şanışer",          "Suç Ortağım"),

    T("Adrenaline",         "Ceza",             "Holocaust"),
    T("Adrenaline",         "UZI",              "Kahraman Olamam"),
    T("Adrenaline",         "Ben Fero",         "Dibine Kadar"),

    T("Hard Reset",         "Ceza",             "Holocaust"),
    T("Hard Reset",         "Ben Fero",         "Dibine Kadar"),
    T("Hard Reset",         "UZI",              "Kahraman Olamam"),

    T("Rage Lift",          "Ceza",             "Holocaust"),
    T("Rage Lift",          "Ben Fero",         "Dibine Kadar"),

    T("Late Night Drive",   "Ezhel",            "Geceler"),
    T("Late Night Drive",   "Sagopa Kajmer",    "Bir Selam Dur"),
    T("Late Night Drive",   "Şanışer",          "Suç Ortağım"),

    T("Smoke & Mirrors",    "Ezhel",            "Geceler"),
    T("Smoke & Mirrors",    "Sagopa Kajmer",    "Bir Selam Dur"),

    T("Hollow",             "Sagopa Kajmer",    "Bir Selam Dur"),
    T("Hollow",             "Ezhel",            "Müptezhel"),

    T("Rainy Window",       "Sagopa Kajmer",    "Bir Selam Dur"),
    T("Rainy Window",       "Ezhel",            "Müptezhel"),

    T("Afterparty",         "Ezhel",            "Geceler"),
    T("Afterparty",         "UZI",              "Kahraman Olamam"),

    # ===================================================================
    # HINDI / BOLLYWOOD
    # ===================================================================

    T("Heartbreak",         "Arijit Singh",     "Tum Hi Ho"),
    T("Heartbreak",         "Arijit Singh",     "Channa Mereya"),
    T("Heartbreak",         "Arijit Singh",     "Ae Dil Hai Mushkil"),
    T("Heartbreak",         "Arijit Singh",     "Tera Yaar Hoon Main"),
    T("Heartbreak",         "Arijit Singh",     "Phir Le Aya Dil"),

    T("Hollow",             "Arijit Singh",     "Tum Hi Ho"),
    T("Hollow",             "Arijit Singh",     "Channa Mereya"),
    T("Hollow",             "AR Rahman",        "Dil Se Re"),

    T("Rainy Window",       "Arijit Singh",     "Channa Mereya"),
    T("Rainy Window",       "Arijit Singh",     "Ae Dil Hai Mushkil"),
    T("Rainy Window",       "AR Rahman",        "Dil Se Re"),

    T("3 AM Unsent Texts",  "Arijit Singh",     "Tum Hi Ho"),
    T("3 AM Unsent Texts",  "Arijit Singh",     "Phir Le Aya Dil"),
    T("3 AM Unsent Texts",  "Arijit Singh",     "Ae Dil Hai Mushkil"),

    T("Acoustic Corner",    "AR Rahman",        "Jai Ho"),
    T("Acoustic Corner",    "Arijit Singh",     "Tum Hi Ho"),
    T("Acoustic Corner",    "AR Rahman",        "Dil Se Re"),

    T("Campfire Sessions",  "AR Rahman",        "Jai Ho"),
    T("Campfire Sessions",  "Arijit Singh",     "Tum Hi Ho"),

    T("Deep Focus",         "AR Rahman",        "Roja Theme"),
    T("Deep Focus",         "AR Rahman",        "Dil Se Re"),
    T("Deep Focus",         "Nucleya",          "Bass Rani"),

    T("Work Mode",          "AR Rahman",        "Roja Theme"),
    T("Work Mode",          "AR Rahman",        "Jai Ho"),
    T("Work Mode",          "Nucleya",          "Bass Rani"),

    T("Afterparty",         "Badshah",          "Paani Paani"),
    T("Afterparty",         "Badshah",          "Genda Phool"),

    T("Villain Arc",        "DIVINE",           "Mere Gully Mein"),
    T("Villain Arc",        "DIVINE",           "Jungli Sher"),
    T("Villain Arc",        "Badshah",          "DJ Waley Babu"),

    T("Adrenaline",         "DIVINE",           "Mere Gully Mein"),
    T("Adrenaline",         "DIVINE",           "Jungli Sher"),
    T("Adrenaline",         "Nucleya",          "Bass Rani"),

    # ===================================================================
    # SPANISH-LANGUAGE ROCK
    # ===================================================================

    T("Acoustic Corner",    "Soda Stereo",      "De Música Ligera"),
    T("Acoustic Corner",    "Café Tacvba",      "Eres"),
    T("Acoustic Corner",    "Los Bunkers",      "Miña Terra"),
    T("Acoustic Corner",    "Caifanes",         "La Negra Tomasa"),
    T("Acoustic Corner",    "Divididos",        "La Flor Azul"),

    T("Campfire Sessions",  "Soda Stereo",      "De Música Ligera"),
    T("Campfire Sessions",  "Café Tacvba",      "Eres"),
    T("Campfire Sessions",  "Los Bunkers",      "Miña Terra"),
    T("Campfire Sessions",  "Divididos",        "La Flor Azul"),

    T("Nostalgia",          "Soda Stereo",      "De Música Ligera"),
    T("Nostalgia",          "Café Tacvba",      "Eres"),
    T("Nostalgia",          "Caifanes",         "La Negra Tomasa"),
    T("Nostalgia",          "Los Bunkers",      "Miña Terra"),

    T("Protest Songs",      "Café Tacvba",      "Eres"),
    T("Protest Songs",      "Los Bunkers",      "Miña Terra"),
    T("Protest Songs",      "Caifanes",         "Afuera"),
    T("Protest Songs",      "Divididos",        "Qué Ves"),

    T("Heartbreak",         "Soda Stereo",      "Persiana Americana"),
    T("Heartbreak",         "Café Tacvba",      "Eres"),
    T("Heartbreak",         "Los Bunkers",      "Miña Terra"),

    T("Hollow",             "Soda Stereo",      "Persiana Americana"),
    T("Hollow",             "Caifanes",         "Afuera"),

    T("Golden Hour",        "Soda Stereo",      "De Música Ligera"),
    T("Golden Hour",        "Café Tacvba",      "Eres"),

    T("Rainy Window",       "Soda Stereo",      "Persiana Americana"),
    T("Rainy Window",       "Café Tacvba",      "Eres"),

    # ===================================================================
    # ITALIAN TRAP / POP
    # ===================================================================

    T("Heartbreak",         "Ultimo",           "Piccola stella"),
    T("Heartbreak",         "Calcutta",         "Cosa mi manchi a fare"),
    T("Heartbreak",         "Madame",           "Voce"),
    T("Heartbreak",         "Achille Lauro",    "Me ne frego"),
    T("Heartbreak",         "Salmo",            "Lunare"),

    T("Hollow",             "Ultimo",           "Piccola stella"),
    T("Hollow",             "Calcutta",         "Cosa mi manchi a fare"),
    T("Hollow",             "Madame",           "Voce"),
    T("Hollow",             "Salmo",            "Lunare"),

    T("Rainy Window",       "Ultimo",           "Piccola stella"),
    T("Rainy Window",       "Calcutta",         "Cosa mi manchi a fare"),
    T("Rainy Window",       "Madame",           "Voce"),

    T("3 AM Unsent Texts",  "Ultimo",           "Piccola stella"),
    T("3 AM Unsent Texts",  "Calcutta",         "Cosa mi manchi a fare"),
    T("3 AM Unsent Texts",  "Salmo",            "Lunare"),

    T("Villain Arc",        "Sfera Ebbasta",    "Rockstar"),
    T("Villain Arc",        "Achille Lauro",    "Me ne frego"),
    T("Villain Arc",        "Salmo",            "90MIN"),

    T("Money Talks",        "Sfera Ebbasta",    "Rockstar"),
    T("Money Talks",        "Sfera Ebbasta",    "BHMG"),
    T("Money Talks",        "Achille Lauro",    "Me ne frego"),

    T("Flex Tape",          "Sfera Ebbasta",    "Rockstar"),
    T("Flex Tape",          "Sfera Ebbasta",    "BHMG"),

    T("Adrenaline",         "Salmo",            "90MIN"),
    T("Adrenaline",         "Sfera Ebbasta",    "Rockstar"),
    T("Adrenaline",         "Achille Lauro",    "Me ne frego"),

    T("Nostalgia",          "Calcutta",         "Cosa mi manchi a fare"),
    T("Nostalgia",          "Ultimo",           "Piccola stella"),

    # ===================================================================
    # RUSSIAN RAP
    # ===================================================================

    T("Hollow",             "IC3PEAK",          "ПЛАК ПЛАК"),
    T("Hollow",             "Monetochka",       "Нет"),
    T("Hollow",             "Oxxxymiron",       "Последний"),
    T("Hollow",             "Face",             "Бoги"),
    T("Hollow",             "Porchy",           "Холодно"),

    T("Rainy Window",       "IC3PEAK",          "ПЛАК ПЛАК"),
    T("Rainy Window",       "Monetochka",       "Нет"),
    T("Rainy Window",       "Porchy",           "Холодно"),
    T("Rainy Window",       "Oxxxymiron",       "Последний"),

    T("3 AM Unsent Texts",  "IC3PEAK",          "ПЛАК ПЛАК"),
    T("3 AM Unsent Texts",  "Monetochka",       "Нет"),
    T("3 AM Unsent Texts",  "Porchy",           "Холодно"),

    T("Overthinking",       "Oxxxymiron",       "Последний"),
    T("Overthinking",       "Porchy",           "Холодно"),
    T("Overthinking",       "IC3PEAK",          "ПЛАК ПЛАК"),

    T("Villain Arc",        "Oxxxymiron",       "Ultima Thule"),
    T("Villain Arc",        "Face",             "Бoги"),
    T("Villain Arc",        "IC3PEAK",          "Один"),

    T("Adrenaline",         "Oxxxymiron",       "Ultima Thule"),
    T("Adrenaline",         "Face",             "Бoги"),

    T("Hard Reset",         "Oxxxymiron",       "Ultima Thule"),
    T("Hard Reset",         "Face",             "Бoги"),
    T("Hard Reset",         "IC3PEAK",          "Один"),

    T("Protest Songs",      "Oxxxymiron",       "Ultima Thule"),
    T("Protest Songs",      "IC3PEAK",          "Один"),
    T("Protest Songs",      "Monetochka",       "Нет"),

    T("Goth / Darkwave",    "IC3PEAK",          "ПЛАК ПЛАК"),
    T("Goth / Darkwave",    "IC3PEAK",          "Один"),
    T("Goth / Darkwave",    "Monetochka",       "Нет"),

    T("Dark Pop",           "IC3PEAK",          "ПЛАК ПЛАК"),
    T("Dark Pop",           "Monetochka",       "Нет"),

    T("Deep Focus",         "Oxxxymiron",       "Последний"),
    T("Deep Focus",         "Porchy",           "Холодно"),

    T("Work Mode",          "Oxxxymiron",       "Последний"),
    T("Work Mode",          "Porchy",           "Холодно"),
]

# ---------------------------------------------------------------------------
# Market label helper (for per-market summary)
# ---------------------------------------------------------------------------

ARTIST_TO_MARKET = {
    "Shabjdeed": "Arabic/MENA",
    "Wegz": "Arabic/MENA",
    "Al Nather": "Arabic/MENA",
    "Marwan Pablo": "Arabic/MENA",
    "Abyusif": "Arabic/MENA",
    "El Rass": "Arabic/MENA",
    "Lege-Cy": "Arabic/MENA",
    "Nekfeu": "French rap",
    "Damso": "French rap",
    "Hamza": "French rap",
    "SCH": "French rap",
    "Freeze Corleone": "French rap",
    "Gazo": "French rap",
    "Ninho": "French rap",
    "Laylow": "French rap",
    "Lomepal": "French rap",
    "Capital Bra": "German rap",
    "Ufo361": "German rap",
    "Bonez MC": "German rap",
    "Loredana": "German rap",
    "Pashanim": "German rap",
    "Rin": "German rap",
    "Apache 207": "German rap",
    "MC Hariel": "Brazilian funk/phonk",
    "Poze do Rodo": "Brazilian funk/phonk",
    "Oruam": "Brazilian funk/phonk",
    "MC Ryan SP": "Brazilian funk/phonk",
    "Menor Nico": "Brazilian funk/phonk",
    "MC Cabelinho": "Brazilian funk/phonk",
    "Ezhel": "Turkish rap/pop",
    "Ceza": "Turkish rap/pop",
    "UZI": "Turkish rap/pop",
    "Sagopa Kajmer": "Turkish rap/pop",
    "Ben Fero": "Turkish rap/pop",
    "Şanışer": "Turkish rap/pop",
    "Arijit Singh": "Hindi/Bollywood",
    "AR Rahman": "Hindi/Bollywood",
    "Badshah": "Hindi/Bollywood",
    "DIVINE": "Hindi/Bollywood",
    "Nucleya": "Hindi/Bollywood",
    "Soda Stereo": "Spanish-language rock",
    "Café Tacvba": "Spanish-language rock",
    "Los Bunkers": "Spanish-language rock",
    "Caifanes": "Spanish-language rock",
    "Divididos": "Spanish-language rock",
    "Sfera Ebbasta": "Italian trap/pop",
    "Ultimo": "Italian trap/pop",
    "Calcutta": "Italian trap/pop",
    "Achille Lauro": "Italian trap/pop",
    "Salmo": "Italian trap/pop",
    "Madame": "Italian trap/pop",
    "Oxxxymiron": "Russian rap",
    "Face": "Russian rap",
    "IC3PEAK": "Russian rap",
    "Monetochka": "Russian rap",
    "Porchy": "Russian rap",
}


def main():
    # Load existing data
    with open(ANCHORS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build existing dedup set per mood: (artist_lower, title_lower)
    existing = defaultdict(set)
    for mood, tracks in data.items():
        for t in tracks:
            existing[mood].add((t["artist"].lower(), t["title"].lower()))

    # Track additions
    added_per_mood = defaultdict(int)
    added_per_market = defaultdict(int)
    skipped_no_mood = defaultdict(int)
    total_added = 0

    for (mood, artist, title) in ADDITIONS:
        if mood not in data:
            skipped_no_mood[mood] += 1
            continue
        key = (artist.lower(), title.lower())
        if key not in existing[mood]:
            data[mood].append({"artist": artist, "title": title})
            existing[mood].add(key)
            market = ARTIST_TO_MARKET.get(artist, "Unknown")
            added_per_mood[mood] += 1
            added_per_market[market] += 1
            total_added += 1

    # Write back
    with open(ANCHORS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Validate JSON
    with open(ANCHORS_PATH, "r", encoding="utf-8") as f:
        json.load(f)
    print("JSON validation: OK")

    # Skipped moods warning
    if skipped_no_mood:
        print(f"\n[INFO] Skipped {sum(skipped_no_mood.values())} entries — mood not found in file:")
        for m, n in sorted(skipped_no_mood.items()):
            print(f"  {m!r}: {n} entries skipped")

    # Summary
    print(f"\n{'='*62}")
    print(f"TOTAL NEW TRACKS ADDED: {total_added}")
    print(f"{'='*62}\n")

    print("PER MARKET:")
    for market in sorted(added_per_market):
        print(f"  {market:<30} {added_per_market[market]:>4} tracks")

    print("\nPER MOOD (sorted by additions):")
    for mood, count in sorted(added_per_mood.items(), key=lambda x: -x[1]):
        print(f"  {mood:<42} +{count}")

    print(f"\nTotal moods with new additions: {len(added_per_mood)}")
    print("Done.")


if __name__ == "__main__":
    main()
