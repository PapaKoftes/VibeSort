"""
patch_packs_international.py

Fixes two systemic language biases in data/packs.json:
  1. Adds international macro genres to preferred_macro_genres for each mood
  2. Adds multilingual seed_phrases so playlist mining finds non-English playlists

Rules:
  - Only ADD values; never remove existing ones
  - Deduplicate (no duplicates per mood)
  - Only use valid macro genre values from core/genre.py MACRO_GENRES list
  - Idempotent: re-running produces the same result
  - Validates JSON after writing
"""

import json
import os
import sys

PACKS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "packs.json")

# ---------------------------------------------------------------------------
# Valid macro genres (from core/genre.py)
# ---------------------------------------------------------------------------
VALID_MACRO_GENRES = {
    "East Coast Rap", "West Coast Rap", "Southern Rap", "Houston Rap",
    "Midwest Rap", "UK Rap / Grime", "French Rap", "Phonk", "Brazilian Phonk",
    "Brazilian / Funk Carioca", "Latin / Reggaeton", "Mexican Regional",
    "R&B / Soul", "Dark R&B", "Electronic / House", "Electronic / Techno",
    "Electronic / Drum & Bass", "Electronic / Bass & Dubstep",
    "Electronic / Trance", "Electronic / Ambient", "Synthwave / Retrowave",
    "Lo-Fi", "Indie / Alternative", "Shoegaze / Dream Pop",
    "Post-Punk / Darkwave", "Emo / Post-Hardcore", "Punk / Hardcore",
    "Metal", "Rock", "Classic Rock", "Jazz / Blues", "Classical / Orchestral",
    "Pop", "K-Pop / J-Pop", "Hyperpop", "Country", "Folk / Americana",
    "Afrobeats / Amapiano", "Caribbean / Reggae", "World / Regional",
    "Ambient / Experimental", "Other",
}

# ---------------------------------------------------------------------------
# Per-mood additions: (genres_to_add, phrases_to_add)
# Key = exact mood name from packs.json
# ---------------------------------------------------------------------------
MOOD_PATCHES: dict[str, tuple[list[str], list[str]]] = {

    # ── INTROSPECTIVE / SAD / HOLLOW ─────────────────────────────────────────
    "Hollow": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["trap arabe sombre", "rap français mélancolie", "arabic sad rap", "música triste rap"],
    ),
    "Midnight Spiral": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap nocturno tristeza", "rap français nuit", "gece hüzün müzik", "ночной рэп грусть"],
    ),
    "3 AM Unsent Texts": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap français 3h du matin", "canciones madrugada soledad", "gece rap türkçe", "rap arabe mélancolie"],
    ),
    "Rainy Window": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap pluvieux français", "música lluvia tristeza", "yağmurda dinlenilen müzik", "arabe pluie sombre"],
    ),
    "Dissolve": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap français déprime", "canciones desolación", "müzik çözülme", "rap arabe introspectif"],
    ),
    "Grief Wave": (
        ["French Rap", "World / Regional", "Latin / Reggaeton"],
        ["canciones de duelo", "chansons de deuil françaises", "müzik yas", "hindi sad songs loss"],
    ),
    "Bedroom Confessions": (
        ["French Rap", "World / Regional", "K-Pop / J-Pop"],
        ["confessions rap français", "canciones íntimas habitación", "방 안 고백 노래", "rap türkçe iç dünya"],
    ),

    # ── DARK / CINEMATIC NIGHT ────────────────────────────────────────────────
    "Late Night Drive": (
        ["French Rap", "World / Regional", "Brazilian Phonk"],
        ["rap nocturno", "conducir de noche música", "gece rap türkçe", "musique nuit conduire"],
    ),
    "Smoke & Mirrors": (
        ["French Rap", "UK Rap / Grime", "World / Regional", "Brazilian Phonk"],
        ["rap français fumée", "música humo nocturna", "gece duman müzik", "rap arabe mystère"],
    ),
    "Slow Burn": (
        ["French Rap", "UK Rap / Grime", "World / Regional", "Brazilian Phonk"],
        ["rap lent français", "música lenta nocturna", "yavaş yakıcı rap", "rap arabe lent"],
    ),
    "Midnight Clarity": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap français minuit réflexion", "canciones claridad nocturna", "gece farkındalık müzik"],
    ),
    "Liminal": (
        ["French Rap", "World / Regional"],
        ["musique liminal française", "música liminal oscura", "eerie müzik geçiş"],
    ),
    "Winter Dark": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap français hiver sombre", "música invierno oscuro", "kış depresyon müzik", "nordisk vinter sorg"],
    ),
    "Overthinking": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap français pensées", "música pensar demasiado", "aşırı düşünme rap", "rap arabe introspectif"],
    ),
    "Midnight Gospel": (
        ["World / Regional", "French Rap"],
        ["musique existentielle nuit", "música existencial madrugada", "gece felsefî müzik"],
    ),

    # ── VILLAIN / AGGRESSIVE / POWER ────────────────────────────────────────
    "Villain Arc": (
        ["French Rap", "UK Rap / Grime", "Brazilian Phonk", "World / Regional"],
        ["rap français agressif", "trap arabe hype", "deutschrap aggro", "rap vilão brasileiro"],
    ),
    "Adrenaline": (
        ["French Rap", "UK Rap / Grime", "Brazilian Phonk", "World / Regional"],
        ["rap agressif français", "música adrenalina trap", "hızlı agresif rap", "musica agressiva brasileira"],
    ),
    "Hard Reset": (
        ["French Rap", "UK Rap / Grime", "Brazilian Phonk", "World / Regional"],
        ["rap rage français", "música ira reset", "öfke müzik", "rap arabe rage"],
    ),
    "Rage Lift": (
        ["French Rap", "UK Rap / Grime", "Brazilian Phonk", "World / Regional"],
        ["rap français salle de sport", "música furia gimnasio", "öfke spor müzik", "trap arabe gym"],
    ),
    "Rage Quit": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap rage français gaming", "música rabia videojuegos", "öfke oyun rap"],
    ),
    "Boxing Ring": (
        ["French Rap", "UK Rap / Grime", "World / Regional", "Brazilian Phonk"],
        ["rap combat français", "música pelea entrada", "dövüş müzik trap", "trap arabe boxe"],
    ),
    "Anti-Hero Receipts": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap anti-héros français", "música anti héroe", "rap karakter türkçe"],
    ),
    "Running Fuel": (
        ["French Rap", "UK Rap / Grime", "Brazilian Phonk", "World / Regional"],
        ["rap français courir", "música correr motivación", "koşu müzik trap", "musica corrida brasileira"],
    ),

    # ── PHONK / DARK TRAP ─────────────────────────────────────────────────────
    "Phonk Season": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["phonk brasileiro", "phonk arabe", "drift phonk türkçe", "phonk français sombre"],
    ),
    "Trap & Chill": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["trap chill français", "trap tranquilo nocturno", "trap sakin türkçe", "trap arabe chill"],
    ),
    "Cloud Rap Haze": (
        ["French Rap", "World / Regional"],
        ["cloud rap français rêveur", "rap nube tranquilo", "bulut rap türkçe"],
    ),
    "Pluggnb Heartache": (
        ["French Rap", "World / Regional"],
        ["pluggnb français", "trap melodique arabe triste", "plugg rap türkçe"],
    ),

    # ── DRILL ─────────────────────────────────────────────────────────────────
    "Drill": (
        ["French Rap", "World / Regional"],
        ["drill uk", "drill français", "trap arabe drill", "drill türkçe"],
    ),
    "Drill Confessions": (
        ["French Rap", "World / Regional"],
        ["drill uk", "drill français", "trap arabe drill", "drill emocional espanol"],
    ),

    # ── FLEX / MONEY ─────────────────────────────────────────────────────────
    "Money Talks": (
        ["French Rap", "World / Regional"],
        ["rap argent français", "rap dinero latino", "para rap türkçe", "rap arabe argent"],
    ),
    "Flex Tape": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap swag français", "rap flow latino", "swag rap türkçe", "rap arabe flex"],
    ),

    # ── HEARTBREAK / EMOTIONAL ───────────────────────────────────────────────
    "Heartbreak": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional", "French Rap"],
        ["canciones de desamor", "chansons tristes françaises", "hindi sad songs", "kalpten gelen şarkılar"],
    ),
    "Heartbreak Hotel": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional", "French Rap"],
        ["canciones de desamor", "chansons tristes", "hindi sad songs", "türkçe aşk acısı şarkılar"],
    ),
    "Sea of Feels": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional", "French Rap"],
        ["canciones llorar desahogo", "chansons émotions débordantes", "감정 폭발 음악", "hissiyat müzik"],
    ),
    "Bedroom Pop Diary": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional"],
        ["pop habitación tristeza", "bedroom pop français diary", "방 팝 일기 음악", "rap türkçe iç günlük"],
    ),
    "Raw Emotion": (
        ["Latin / Reggaeton", "World / Regional", "French Rap"],
        ["canciones sentimientos crudos", "chansons émotions brutes", "ham duygu müzik"],
    ),
    "Breakup Bravado": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional", "French Rap"],
        ["canciones empoderamiento ruptura", "chansons rupture fierté", "ayrılık güç şarkıları"],
    ),
    "Songs About Goodbye": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional"],
        ["canciones de despedida", "chansons adieu françaises", "veda şarkıları", "작별 노래"],
    ),
    "Shoegaze Breakups": (
        ["World / Regional", "French Rap"],
        ["shoegaze ruptura français", "shoegaze desamor español", "shoegaze kırık kalp"],
    ),

    # ── PARTY / DANCE ─────────────────────────────────────────────────────────
    "Afterparty": (
        ["Brazilian / Funk Carioca", "Afrobeats / Amapiano", "Caribbean / Reggae", "Mexican Regional"],
        ["baile funk depois da festa", "afrobeats after party", "reggaeton madrugada", "fiesta después de noche"],
    ),
    "Club Warm-Up": (
        ["Brazilian / Funk Carioca", "Afrobeats / Amapiano", "Caribbean / Reggae", "Mexican Regional", "Latin / Reggaeton"],
        ["baile funk aquecimento", "reggaeton club apertura", "afrobeats warm up", "club açılış müzik"],
    ),
    "Latin Heat": (
        ["Mexican Regional", "World / Regional"],
        ["reggaeton caliente", "baile funk festão", "música latina caliente", "corrido fiesta"],
    ),
    "Tropicana": (
        ["Mexican Regional", "World / Regional"],
        ["reggaeton tropical", "funk carioca praia", "afrobeats island vibes", "tropical corridos"],
    ),
    "Dance Alone": (
        ["Brazilian / Funk Carioca", "Afrobeats / Amapiano", "Latin / Reggaeton"],
        ["baile funk sozinho", "reggaeton bailar sola", "afrobeats dançar sozinho", "tek başına dans müzik"],
    ),
    "Disco Lights": (
        ["Latin / Reggaeton", "Afrobeats / Amapiano", "Brazilian / Funk Carioca"],
        ["disco reggaeton mix", "afrobeats disco", "baile funk disco", "latein disco latin"],
    ),
    "Overflow": (
        ["Brazilian / Funk Carioca", "Afrobeats / Amapiano", "Latin / Reggaeton"],
        ["funk carioca euforia", "afrobeats euphoria", "reggaeton eufórico", "coşku müzik"],
    ),
    "Euphoric Rave": (
        ["Brazilian / Funk Carioca", "Afrobeats / Amapiano", "World / Regional"],
        ["baile funk rave", "afrobeats rave clube", "coşku rave müzik"],
    ),
    "Queer Dance Confetti": (
        ["Latin / Reggaeton", "Brazilian / Funk Carioca", "Afrobeats / Amapiano"],
        ["reggaeton queer pride", "funk carioca lgbt", "afrobeats pride party"],
    ),

    # ── LO-FI / FOCUS / STUDY ────────────────────────────────────────────────
    "Deep Focus": (
        ["K-Pop / J-Pop", "World / Regional", "French Rap"],
        ["música para estudar", "musique concentration française", "공부 음악", "çalışma müzik"],
    ),
    "Lo-Fi Flow": (
        ["K-Pop / J-Pop", "World / Regional", "French Rap"],
        ["lofi japonés estudiar", "lofi musique française", "로파이 공부 음악", "lofi çalışma"],
    ),
    "Work Mode": (
        ["K-Pop / J-Pop", "World / Regional", "French Rap"],
        ["música para estudar", "musique concentration française", "공부 집중 음악", "çalışma odak müzik"],
    ),
    "Coffee Shop Folk": (
        ["K-Pop / J-Pop", "World / Regional", "Latin / Reggaeton"],
        ["café música acústica española", "musique café folk français", "카페 음악 한국", "kahve dükkanı müzik"],
    ),
    "Chillhop Cafe": (
        ["K-Pop / J-Pop", "World / Regional"],
        ["chillhop japonés café", "jazz hop café français", "카페 재즈 힙합", "café müzik relaxant"],
    ),

    # ── FOLK / ACOUSTIC ──────────────────────────────────────────────────────
    "Campfire Sessions": (
        ["Latin / Reggaeton", "World / Regional"],
        ["canciones campamento guitarra", "chansons guitare feu de camp", "kamp ateşi müzik gitar"],
    ),
    "Acoustic Corner": (
        ["Latin / Reggaeton", "World / Regional"],
        ["música acústica española guitarra", "musique acoustique française", "akustik köşe müzik"],
    ),
    "Coffee Shop Folk": (
        ["K-Pop / J-Pop", "World / Regional", "Latin / Reggaeton"],
        ["café música acústica española", "musique café folk français", "카페 음악 한국", "kahve dükkanı müzik"],
    ),
    "Folk & Feel": (
        ["Latin / Reggaeton", "World / Regional"],
        ["folk latino guitarra", "musique folk sentiment", "folk hissi gitar", "música folk emocional"],
    ),
    "Campfire Sessions": (
        ["Latin / Reggaeton", "World / Regional"],
        ["canciones campamento guitarra", "chansons guitare feu de camp", "kamp ateşi müzik gitar"],
    ),
    "Songs About Home": (
        ["Latin / Reggaeton", "World / Regional", "K-Pop / J-Pop"],
        ["canciones del hogar latino", "chansons maison française", "고향 노래", "ev özlemi müzik"],
    ),

    # ── PROTEST / POLITICAL ──────────────────────────────────────────────────
    "Protest Songs": (
        ["Latin / Reggaeton", "World / Regional", "French Rap"],
        ["canciones protesta latina", "rap contestataire français", "isyan müzik türkçe", "musik protes dunia"],
    ),

    # ── NOSTALGIA ────────────────────────────────────────────────────────────
    "Nostalgia": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional"],
        ["canciones nostalgia latina", "chansons nostalgie françaises", "nostalji müzik türkçe", "추억 노래"],
    ),
    "Classic Rewind": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional"],
        ["éxitos clásicos latinos", "classiques français nostalgie", "klasik türkçe nostalji", "옛날 명곡"],
    ),
    "Old School Hip-Hop": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap classique français 90s", "uk rap classic", "klasik rap türkçe", "rap vintage arabe"],
    ),

    # ── EMOTIONAL / HEALING ──────────────────────────────────────────────────
    "Healing Kind": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional"],
        ["canciones sanación latina", "chansons guérison françaises", "치유 음악 한국", "iyileşme müzik"],
    ),
    "Sunday Reset": (
        ["K-Pop / J-Pop", "World / Regional", "Latin / Reggaeton"],
        ["música domingo descanso", "musique dimanche recharge", "일요일 힐링 음악", "pazar dinlenme müzik"],
    ),
    "Soft Hours": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional"],
        ["canciones suaves latinas", "musique douce française", "부드러운 음악", "yumuşak müzik"],
    ),
    "Tenderness": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional"],
        ["canciones ternura romántica", "chansons tendresse françaises", "사랑 부드러운 음악", "nazik aşk müzik"],
    ),
    "Slow Jams": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional"],
        ["slow jams latino romantico", "musique lente romantic française", "슬로우 잼 한국", "yavaş romantik müzik"],
    ),
    "Golden Hour": (
        ["Latin / Reggaeton", "Afrobeats / Amapiano", "World / Regional"],
        ["hora dorada música latina", "golden hour afrobeats", "altın saat müzik", "hora de ouro afrobeats"],
    ),
    "Sundown": (
        ["Latin / Reggaeton", "Afrobeats / Amapiano", "World / Regional"],
        ["atardecer música latina", "coucher de soleil musique", "gün batımı müzik", "afrobeats sunset"],
    ),
    "Weightless": (
        ["World / Regional", "K-Pop / J-Pop"],
        ["música sin peso etéreo", "musique apesanteur française", "무중력 음악", "hafiflik müzik"],
    ),

    # ── TRAVEL / OPEN ROAD ───────────────────────────────────────────────────
    "Open Road": (
        ["Latin / Reggaeton", "World / Regional", "French Rap"],
        ["música ruta carretera", "musique route ouverte française", "açık yol müzik", "reggaeton ruta"],
    ),
    "Runaway Highways": (
        ["Latin / Reggaeton", "World / Regional", "French Rap"],
        ["escapar música carretera", "fuite route musique française", "kaçış yol müzik"],
    ),
    "New City Energy": (
        ["Latin / Reggaeton", "Afrobeats / Amapiano", "World / Regional"],
        ["nueva ciudad energía latina", "nouvelle ville énergie française", "yeni şehir enerji müzik"],
    ),

    # ── GENRE-SPECIFIC (expanding coverage) ──────────────────────────────────
    "Amapiano Sunset": (
        ["Latin / Reggaeton", "Caribbean / Reggae"],
        ["amapiano tarde relajado", "amapiano coucher soleil", "amapiano günbatımı"],
    ),
    "Afro-Fusion Golden Hour": (
        ["Latin / Reggaeton", "Caribbean / Reggae"],
        ["afrobeats fusion dorado", "afro fusion heure dorée", "afro füzyon altın saat"],
    ),
    "Latin Ballroom Heat": (
        ["Mexican Regional", "World / Regional"],
        ["bachata sensual caliente", "salsa romantica caliente", "latin dansı ateşli"],
    ),
    "Brass & Drumline Energy": (
        ["Latin / Reggaeton", "Afrobeats / Amapiano"],
        ["música marcha latina hype", "afrobeats brass energy", "nefesli davul enerji"],
    ),

    # ── DARK AESTHETIC ────────────────────────────────────────────────────────
    "Dark Pop": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["pop sombre français", "pop oscuro español", "karanlık pop türkçe"],
    ),
    "Goth / Darkwave": (
        ["French Rap", "World / Regional"],
        ["goth musique française", "musica oscura gótica", "gotik müzik karanlık"],
    ),
    "Dream Pop Haze": (
        ["World / Regional", "K-Pop / J-Pop"],
        ["dream pop français rêveur", "dream pop japonés ensueño", "rüya pop müzik"],
    ),
    "Industrial Gothic Floor": (
        ["French Rap", "World / Regional"],
        ["industriel gothique français", "industrial gótico español", "endüstriyel gotik müzik"],
    ),

    # ── CINEMATIC / EPIC ─────────────────────────────────────────────────────
    "Cinematic Swell": (
        ["World / Regional", "Latin / Reggaeton"],
        ["música cinematográfica latina", "musique cinématographique française", "sinematik müzik"],
    ),
    "Epic Gaming": (
        ["World / Regional", "K-Pop / J-Pop"],
        ["música épica gaming latina", "musique épique jeu vidéo", "epik oyun müzik", "서사적 게임 음악"],
    ),

    # ── MORNING / POSITIVE ───────────────────────────────────────────────────
    "Morning Ritual": (
        ["Latin / Reggaeton", "Afrobeats / Amapiano", "World / Regional"],
        ["música mañana positiva", "musique matin positive française", "sabah ritüeli müzik", "afrobeats morning"],
    ),
    "Neo-Soul": (
        ["Latin / Reggaeton", "World / Regional", "Afrobeats / Amapiano"],
        ["neo soul latino", "neo soul africain", "neo soul türkçe", "afrobeats soul fusion"],
    ),
    "Acoustic Soul": (
        ["Latin / Reggaeton", "World / Regional"],
        ["soul acústico latino", "soul acoustique français", "akustik ruh müzik"],
    ),
    "Jazz Nights": (
        ["Latin / Reggaeton", "World / Regional"],
        ["jazz latino nocturno", "jazz manouche français nuit", "gece caz müzik"],
    ),

    # ── RETRO / SYNTHWAVE ────────────────────────────────────────────────────
    "Retro Future": (
        ["Latin / Reggaeton", "World / Regional", "K-Pop / J-Pop"],
        ["synthpop retro latino", "rétrofuturisme synthpop français", "retro synthpop Türkiye", "시티팝 레트로"],
    ),
    "Synthwave Nights": (
        ["World / Regional", "K-Pop / J-Pop"],
        ["synthwave noche español", "synthwave nuit française", "synthwave gece türkçe"],
    ),
    "Vaporwave": (
        ["World / Regional", "K-Pop / J-Pop"],
        ["vaporwave japonés", "vaporwave esthétique français", "vaporwave estetik türkçe"],
    ),

    # ── SPECIFIC NICHE MOODS ─────────────────────────────────────────────────
    "Breakup Bravado": (
        ["Latin / Reggaeton", "K-Pop / J-Pop", "World / Regional", "French Rap"],
        ["canciones empoderamiento ruptura", "chansons rupture fierté", "ayrılık güç şarkıları"],
    ),
    "Psychedelic": (
        ["World / Regional", "Latin / Reggaeton"],
        ["música psicodélica latina", "musique psychédélique française", "psikedelik müzik"],
    ),
    "Emo Hour": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["emo rap français", "emo en español", "emo rap türkçe"],
    ),
    "Indie Bedroom": (
        ["French Rap", "K-Pop / J-Pop", "World / Regional"],
        ["indie chambre français", "indie habitación español", "indie bedroom 한국", "indie yatak odası türkçe"],
    ),
    "Meditation Bath": (
        ["World / Regional", "K-Pop / J-Pop"],
        ["meditación música latina", "méditation musique française", "명상 음악 한국", "meditasyon müzik"],
    ),
    "Hyperpop": (
        ["K-Pop / J-Pop", "World / Regional"],
        ["hyperpop français chaos", "hyperpop japonés", "hyperpop kaotik türkçe"],
    ),
    "Hyperpop Emotional Crash": (
        ["K-Pop / J-Pop", "World / Regional"],
        ["hyperpop triste français", "hyperpop emocional español", "hyperpop duygusal türkçe"],
    ),
    "Piano Bar": (
        ["Latin / Reggaeton", "World / Regional"],
        ["bar de piano latino", "bar à piano jazz français", "piyano bar müzik"],
    ),
    "Midnight Clarity": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["rap français minuit réflexion", "canciones claridad nocturna", "gece farkındalık müzik"],
    ),
    "Baroque Pop Melodrama": (
        ["World / Regional", "Latin / Reggaeton"],
        ["pop barroco melodramático español", "pop baroque mélodramatique français", "barok pop dramatik"],
    ),
    "Warehouse Techno": (
        ["World / Regional"],
        ["techno almacén alemán", "techno entrepôt français", "depo techno türkçe"],
    ),
    "Minimal Techno Tunnel": (
        ["World / Regional"],
        ["techno minimal español", "techno minimal français", "minimal techno türkçe"],
    ),
    "Anime OST Energy": (
        ["World / Regional"],
        ["anime openings japonés workout", "anime ost énergie", "anime ost enerji türkçe"],
    ),
    "J-Pop": (
        [],   # already has World / Regional
        ["j-pop japonais populaire", "música pop japonesa actual", "japon pop türkçe"],
    ),
    "J-Metal": (
        [],
        ["metal japonais français", "metal japonés español", "japon metal türkçe"],
    ),
    "K-Pop Zone": (
        [],
        ["kpop français playlist", "kpop español playlist", "kpop türkçe liste"],
    ),
    "Anime Openings": (
        [],
        ["anime openings japonais", "aperturas anime español", "anime açılışlar türkçe"],
    ),
    "Anime Endings": (
        [],
        ["anime endings japonais", "endings anime español", "anime bitişler türkçe"],
    ),
    "Classical Calm": (
        ["World / Regional"],
        ["música clásica calma latina", "classique calme français", "klasik sakin müzik"],
    ),
    "Neo-Soul": (
        ["Latin / Reggaeton", "World / Regional", "Afrobeats / Amapiano"],
        ["neo soul latino", "neo soul africain", "neo soul türkçe", "afrobeats soul fusion"],
    ),
    "Gospel Fire": (
        ["World / Regional", "Afrobeats / Amapiano", "Latin / Reggaeton"],
        ["gospel africano fuego", "gospel latino adoración", "afrobeats worship", "gospel türkçe övgü"],
    ),
    "Metal Storm": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["metal stürm français", "metal tormenta español", "metal fırtına türkçe"],
    ),
    "Punk Sprint": (
        ["French Rap", "UK Rap / Grime", "World / Regional"],
        ["punk français sprint", "punk sprint español", "punk sprint türkçe"],
    ),
    "Country Roads": (
        ["World / Regional", "Latin / Reggaeton"],
        ["country carretera latino", "country route campagne français", "country yol türkçe"],
    ),
    "Country Story Hour": (
        ["World / Regional"],
        ["country historia español", "country histoire française", "country hikaye türkçe"],
    ),
    "Metal Testimony": (
        ["World / Regional"],
        ["metal testimony español", "metal témoignage français", "metal tanıklık türkçe"],
    ),
    "Symphonic Metal Epics": (
        ["World / Regional"],
        ["metal sinfónico épico español", "métal symphonique épique français", "senfonik metal türkçe"],
    ),
    "Kawaii Metal Sparkle": (
        [],
        ["kawaii metal japonais", "kawaii metal español", "kawaii metal türkçe"],
    ),
    "Shoegaze Breakups": (
        ["World / Regional"],
        ["shoegaze ruptura español", "shoegaze rupture français", "shoegaze kırılma türkçe"],
    ),
    "Baroque Pop Melodrama": (
        ["World / Regional", "Latin / Reggaeton"],
        ["pop barroco melodramático español", "pop baroque mélodramatique français", "barok pop dramatik"],
    ),
    "Sea Shanty Singalong": (
        [],   # genuinely English-specific tradition; keep narrow
        ["canciones marineras españolas", "chansons de marin françaises"],
    ),
    "Same Vibe Different Genre": (
        ["Latin / Reggaeton", "French Rap", "UK Rap / Grime", "Afrobeats / Amapiano",
         "K-Pop / J-Pop", "Brazilian / Funk Carioca", "World / Regional"],
        ["vibra diferente género", "même vibe genre différent", "aynı his farklı tür"],
    ),
}


def patch_packs(packs_path: str) -> None:
    with open(packs_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    moods: dict = data["moods"]

    total_moods_updated = 0
    total_genres_added = 0
    total_phrases_added = 0

    for mood_name, (genres_to_add, phrases_to_add) in MOOD_PATCHES.items():
        if mood_name not in moods:
            # Mood not present in this version of packs.json — skip silently
            continue

        mood = moods[mood_name]
        existing_genres: list = mood.setdefault("preferred_macro_genres", [])
        existing_phrases: list = mood.setdefault("seed_phrases", [])

        existing_genre_set = set(existing_genres)
        existing_phrase_set = set(existing_phrases)

        mood_genres_added = 0
        mood_phrases_added = 0

        for g in genres_to_add:
            assert g in VALID_MACRO_GENRES, f"Invalid macro genre '{g}' for mood '{mood_name}'"
            if g not in existing_genre_set:
                existing_genres.append(g)
                existing_genre_set.add(g)
                mood_genres_added += 1

        for p in phrases_to_add:
            if p not in existing_phrase_set:
                existing_phrases.append(p)
                existing_phrase_set.add(p)
                mood_phrases_added += 1

        if mood_genres_added > 0 or mood_phrases_added > 0:
            total_moods_updated += 1
            total_genres_added += mood_genres_added
            total_phrases_added += mood_phrases_added
            print(f"  [{mood_name}] +{mood_genres_added} genres, +{mood_phrases_added} phrases")

    # Validate and write
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    # Sanity-check: must re-parse without error
    json.loads(json_str)

    with open(packs_path, "w", encoding="utf-8") as f:
        f.write(json_str)
        f.write("\n")

    print()
    print("=" * 60)
    print(f"SUMMARY")
    print(f"  Moods updated    : {total_moods_updated}")
    print(f"  Genres added     : {total_genres_added}")
    print(f"  Phrases added    : {total_phrases_added}")
    print(f"  JSON valid       : YES")
    print("=" * 60)


if __name__ == "__main__":
    abs_path = os.path.abspath(PACKS_PATH)
    print(f"Patching: {abs_path}")
    print()
    patch_packs(abs_path)
