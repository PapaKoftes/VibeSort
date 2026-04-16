"""
scripts/patch_lastfm_tags.py

1. Add the 23 new moods to data/mood_lastfm_tags.json (it only has 87 entries)
2. Add non-English Last.fm tags to all moods that have international emotional
   equivalents — so Arabic, French, German, Brazilian, Korean etc. playlists
   surface in tag chart mining.

Idempotent — re-running is safe.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "mood_lastfm_tags.json")

with open(PATH, encoding="utf-8") as f:
    tags = json.load(f)

print(f"Existing moods: {len(tags)}")

# ── 1. New moods (23) with their Last.fm tag vocabulary ──────────────────────
NEW_MOODS = {
    "Cinematic Swell":      ["cinematic", "epic", "orchestral", "film score", "soundtrack"],
    "Breakup Bravado":      ["breakup", "empowerment", "moving on", "independence", "girl power"],
    "Campfire Sessions":    ["campfire", "acoustic", "folk", "storytelling", "unplugged"],
    "Running Fuel":         ["running", "workout", "cardio", "motivation", "energetic"],
    "Grief Wave":           ["grief", "mourning", "loss", "sad", "healing"],
    "Piano Bar":            ["piano", "jazz", "lounge", "sophisticated", "elegant"],
    "Trap & Chill":         ["trap", "chill", "relaxed", "lo-fi", "smooth"],
    "Coffee Shop Folk":     ["coffee shop", "folk", "acoustic", "cozy", "indie"],
    "Boxing Ring":          ["workout", "boxing", "aggressive", "hype", "intensity"],
    "New City Energy":      ["new beginnings", "city", "urban", "motivation", "energy"],
    "Acoustic Soul":        ["acoustic", "soul", "r&b", "heartfelt", "organic"],
    "Retro Future":         ["synthwave", "retro", "80s", "futuristic", "neon"],
    "Winter Dark":          ["winter", "dark", "cold", "atmospheric", "melancholy"],
    "Protest Songs":        ["protest", "political", "social justice", "resistance", "folk"],
    "Epic Gaming":          ["gaming", "epic", "intense", "boss battle", "orchestral"],
    "Club Warm-Up":         ["club", "warm up", "pre-party", "house", "electronic"],
    "Midnight Gospel":      ["ambient", "atmospheric", "spiritual", "late night", "introspective"],
    "Work Mode":            ["focus", "productivity", "work", "concentration", "study"],
    "Bedroom Confessions":  ["bedroom pop", "intimate", "confessional", "soft", "vulnerable"],
    "Sea of Feels":         ["emotional", "melancholy", "atmospheric", "introspective", "sad"],
    "Dance Alone":          ["dance", "euphoric", "happy", "carefree", "joyful"],
    "Rage Quit":            ["metal", "angry", "aggressive", "heavy", "intense"],
    "Tenderness":           ["tender", "gentle", "love", "soft", "intimate"],
}

added_moods = 0
for mood, mood_tags in NEW_MOODS.items():
    if mood not in tags:
        tags[mood] = mood_tags
        added_moods += 1

# ── 2. International tag additions to existing moods ─────────────────────────
# Last.fm is used globally — these tags are real Last.fm vocabulary that users
# in non-English markets actually apply to tracks. Adding them means the
# tag chart mining step surfaces Arabic, French, German, etc. tracks that
# share the same emotional register as the mood.

INTERNATIONAL_ADDITIONS = {
    # Dark / introspective moods
    "Hollow":               ["arab phonk", "rap français sombre", "trap arabe", "musique triste"],
    "3 AM Unsent Texts":    ["nuit sombre", "insomnia arabe", "rap nuit"],
    "Rainy Window":         ["pluie", "melancolia", "regen", "chansons tristes"],
    "Midnight Spiral":      ["trap arabe", "arabic sad", "rap nocturno"],
    "Dissolve":             ["triste", "melancolico", "arabic emotional"],
    "Smoke & Mirrors":      ["trap arabe", "rap sombre", "french dark rap"],
    "Grief Sequence":       ["دردناک", "trauer", "deuil", "luto"],
    "Grief Wave":           ["grief arabic", "musique deuil", "trauermusik"],
    "Winter Dark":          ["inverno", "hiver sombre", "зима грустная"],
    "Sea of Feels":         ["sensations", "kpop sad", "arabic emotional"],

    # Power / energy moods
    "Villain Arc":          ["rap français agressif", "trap arabe hype", "deutschrap aggro",
                             "arabic hype", "trap duro"],
    "Adrenaline":           ["deutschrap energie", "trap arabe énergie", "rap dur"],
    "Rage Lift":            ["deutschrap aggro", "trap arabe rage", "rap agressif"],
    "Hard Reset":           ["reinicio", "recommencer", "neuanfang"],
    "Boxing Ring":          ["trap arabe boxe", "rap agressif sport"],
    "Rage Quit":            ["metal alemão", "metal français", "metal japonés"],

    # Night / drive / atmospheric
    "Late Night Drive":     ["conducir de noche", "nuit nocturne", "gece arabası",
                             "arabic night drive", "phonk brasileiro noturno"],
    "Phonk Season":         ["phonk brasileiro", "phonk arabe", "arabic phonk",
                             "drift phonk"],
    "Night Owl":            ["noche", "nuit", "nacht", "noite"],

    # Heartbreak / emotional
    "Heartbreak Hotel":     ["canciones de desamor", "chansons tristes", "hindi sad songs",
                             "kpop heartbreak", "arabic breakup", "desamor"],
    "Bedroom Pop Diary":    ["pop de quarto", "pop bedroom français", "kpop bedroom"],
    "Bedroom Confessions":  ["confessions intimes", "arabic emotional pop"],
    "Breakup Bravado":      ["empowerment latina", "kpop girl power", "rap français empowerment"],

    # Chill / focus
    "Deep Focus":           ["musique de concentration", "música para estudar",
                             "공부 음악", "Musik zum Lernen", "موسيقى للدراسة"],
    "Work Mode":            ["música para trabajar", "musique travail",
                             "musik arbeit", "موسيقى عمل"],
    "Lo-Fi Corner":         ["lofi brasileiro", "lofi japonés", "lofi coréen"],
    "Coffee Shop Folk":     ["café folk", "kaffeehaus musik", "música de café"],
    "Acoustic Corner":      ["acoustique français", "música acústica", "akustik türkçe"],

    # Party / dance
    "Afterparty":           ["after party brasil", "soirée française", "after karşısı"],
    "Club Warm-Up":         ["calentamiento", "préchauffage", "aufwärmen", "قبل الحفلة"],
    "Dance Alone":          ["bailar solo", "danser seul", "alleine tanzen"],
    "Latin Heat":           ["reggaeton", "salsa", "bachata", "cumbia", "latin dance"],

    # Folk / roots / acoustic
    "Folk & Feel":          ["folk latinoamericano", "musique folk française",
                             "española folk", "folk mundial"],
    "Campfire Sessions":    ["camp folk", "folk acoustique", "música de fogata"],
    "Protest Songs":        ["nueva canción", "rap protest français", "chanson engagée",
                             "protestsong", "música protesta"],
    "Road Songs":           ["canciones de viaje", "chansons de route", "arabalık müzik"],

    # Cinematic / expansive
    "Cinematic Swell":      ["música de filme", "musique de film", "filmmusik", "موسيقى أفلام"],
    "Epic Gaming":          ["musique jeu vidéo", "videospiel musik", "موسيقى العاب"],

    # Soul / R&B
    "Acoustic Soul":        ["soul français", "soul arabic", "alma acústica"],
    "Neo Soul":             ["soul neo français", "neo soul brasileiro"],
    "Slow Jams":            ["slow jam français", "slow arabe", "slow brasileiro"],

    # Instrumental / ambient
    "Meditation Bath":      ["méditation", "meditacion", "meditasyon", "تأمل"],
    "Midnight Gospel":      ["ambient arabe", "ambient nocturno", "ambient nocturne"],
    "Piano Bar":            ["piano bar français", "piano bar japonés", "бар пианино"],

    # Trap & sub-genres
    "Trap & Chill":         ["trap chill français", "trap chill arabe", "trap chill brasileiro"],
    "Drill Mode":           ["drill français", "drill uk", "arabic drill", "drill brasileiro"],
    "Drill Confessions":    ["drill confession french", "arabic drill sad"],

    # Nostalgic
    "Nostalgia":            ["nostalgia latina", "nostalgie française", "nostalji türk",
                             "arabic nostalgia"],

    # Retro / synth
    "Retro Future":         ["synthwave français", "synthwave japonés", "ретровейв"],
    "Synthwave Nights":     ["synthwave latin", "nuit synthwave", "synthwave nocturno"],

    # New beginnings / energy
    "New City Energy":      ["nueva ciudad", "nouvelle ville", "neue stadt"],
    "Running Fuel":         ["música para correr", "musique course", "koşu müziği"],
}

added_tags = 0
for mood, new_tags in INTERNATIONAL_ADDITIONS.items():
    if mood in tags:
        existing_set = set(tags[mood])
        for t in new_tags:
            if t not in existing_set:
                tags[mood].append(t)
                existing_set.add(t)
                added_tags += 1

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(tags, f, ensure_ascii=False, indent=2)

# Verify
with open(PATH, encoding="utf-8") as f:
    verify = json.load(f)
print(f"Added {added_moods} new moods")
print(f"Added {added_tags} international tags across existing moods")
print(f"Total moods now: {len(verify)}")
print("JSON valid: OK")
