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
  lyr_family · lyr_friends · lyr_jealousy · lyr_summer · lyr_city · lyr_ocean

LANGUAGE COVERAGE
=================
Keyword matching covers:
  Latin-script:  English, Spanish, French, Portuguese, German, Italian, Dutch
  Romanized:     Arabic (transliterated), Korean (transliterated), Hindi (transliterated)
  Native script: Korean (Hangul), Japanese (Hiragana/Katakana/Kanji),
                 Chinese (Simplified), Arabic, Hindi (Devanagari), Russian (Cyrillic)

Native-script keywords use substring matching against the full lowercased lyric text.
Romanized keywords are also kept for mixed-script lyrics (e.g. Romanized K-pop fansites).

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
    # ── Core moods ────────────────────────────────────────────────────────────────
    # EN / ES / FR / PT / DE / IT / NL + transliterated AR / KO / HI
    "sad": [
        # English
        "crying", "tears", "broken heart", "alone tonight", "miss you", "goodbye",
        "heartbreak", "heartbroken", "depression", "grief", "mourning", "lonely",
        "sobbing", "weeping", "shattered", "devastated", "miserable",
        # Spanish
        "llorar", "lágrimas", "corazón roto", "soledad", "tristeza", "dolor",
        "perdido", "extrañar", "adiós", "depresión", "sufriendo", "llorando",
        # French
        "pleurer", "larmes", "coeur brisé", "seul", "tristesse", "douleur",
        "manquer", "adieu", "dépression", "chagrin", "pleures",
        # Portuguese
        "chorar", "lágrimas", "coração partido", "sozinho", "tristeza", "saudade",
        "sofrendo", "perdido", "chorando",
        # German
        "weinen", "tränen", "allein", "vermissen", "traurig", "traurigkeit",
        "einsamkeit", "herzschmerz", "gebrochenes herz", "abschied", "verlassen",
        # Italian
        "piangere", "lacrime", "cuore spezzato", "solo", "tristezza", "dolore",
        "mancare", "addio", "depressione", "soffro",
        # Dutch
        "huilen", "tranen", "gebroken hart", "alleen", "verdriet", "pijn",
        "missen", "vaarwel", "depressie",
        # Korean transliterated
        "bogoshipda", "neomu ulgo sipeo", "uli nal", "biyeol",
        # Korean native (Hangul) — substring match on full text
        "슬퍼", "눈물", "외로워", "이별", "보고싶어", "힘들어", "울고싶어", "그리워",
        # Japanese native — substring match
        "悲しい", "涙", "泣きたい", "寂しい", "辛い", "一人ぼっち", "悲しみ",
        # Chinese native — substring match (multi-char phrases to avoid false positives)
        "难过", "泪水", "哭泣", "寂寞", "思念", "伤心", "孤独", "泪流",
        # Arabic native
        "حزين", "حزينة", "دموع", "بكاء", "وحيد", "وحيدة", "ألم",
        # Hindi native (Devanagari)
        "दुख", "रोना", "अकेला", "दर्द", "आँसू", "तन्हा",
        # Russian native (Cyrillic)
        "плакать", "слёзы", "грустно", "одинок", "тоска", "боль",
        # Hindi transliterated
        "rona", "aansu", "tanha", "dard", "judai", "alvida",
    ],
    "angry": [
        # English
        "hatred", "rage", "furious", "revenge", "enemy", "destroy", "violence",
        "bloodshed", "wrath", "ruthless", "murderous", "vengeance",
        # Spanish
        "odio", "rabia", "furioso", "venganza", "destruir", "violencia", "matar",
        "ira", "enojo", "rencor",
        # French
        "haine", "rage", "furieux", "vengeance", "détruire", "violence",
        "colère", "rancœur",
        # Portuguese
        "ódio", "raiva", "furioso", "vingança", "destruir", "ira", "rancor",
        # German
        "hass", "wut", "wütend", "rache", "zerstören", "feind", "zorn",
        # Italian
        "odio", "rabbia", "furioso", "vendetta", "distruggere", "violenza",
        "ira", "nemico",
        # Dutch
        "haat", "woede", "woedend", "wraak", "vernietigen", "geweld", "vijand",
        # Arabic transliterated
        "ghadab", "haqad",
        # Arabic native
        "غضب", "كره", "أكره", "عدو", "انتقام", "ألم",
        # Korean native
        "화가나", "미워", "분노", "증오",
        # Japanese native
        "怒り", "憎い", "許せない", "怒鳴る", "憎しみ",
        # Chinese native
        "愤怒", "恨", "讨厌", "愤恨", "仇恨",
        # Hindi native
        "गुस्सा", "नफरत", "बदला",
        # Russian native
        "ненависть", "злость", "гнев", "месть",
        # Hindi transliterated
        "gussa", "nafrat", "badla",
    ],
    "love": [
        # English
        "i love you", "falling in love", "kiss me", "beautiful girl", "forever together",
        "darling", "romance", "adore you", "cherish", "devoted", "soulmate",
        # Spanish
        "te amo", "te quiero", "amor", "besarte", "hermosa", "corazón", "enamorado",
        "romantico", "adorar", "cariño", "mi amor", "mi vida",
        # French
        "je t'aime", "amour", "t'embrasser", "belle", "chérie", "mon coeur",
        "toujours ensemble", "tu me manques",
        # Portuguese
        "eu te amo", "amor", "beijar", "linda", "querida", "coração",
        "para sempre", "meu bem",
        # Arabic transliterated
        "habibi", "habibti", "hayati", "albi", "ahebek", "eshqi", "omri",
        "rohi", "ya albi",
        # German
        "ich liebe dich", "liebe", "küssen", "für immer", "liebling", "mein herz",
        "schönste", "verliebt", "romantisch", "du bist alles",
        # Italian
        "ti amo", "amore", "baciarti", "bella", "tesoro", "cuore mio",
        "per sempre", "innamorato", "romantico",
        # Dutch
        "ik hou van jou", "liefde", "kussen", "mooi", "schat", "voor altijd",
        "verliefd", "romantisch",
        # Korean transliterated
        "saranghae", "saranghaeyo", "bogoshipda", "neomu joha",
        # Korean native
        "사랑해", "사랑", "보고싶어", "그리워", "사랑하나", "좋아해",
        # Japanese native
        "愛してる", "好きだよ", "愛情", "恋しい", "大好き", "あなたが好き", "恋",
        # Chinese native (multi-char phrases only to avoid false positives from single 爱)
        "我爱你", "爱情", "爱你", "喜欢你", "心爱", "爱人",
        # Arabic native
        "أحبك", "حبيبي", "حبيبتي", "قلبي", "عشقتك",
        # Hindi native
        "प्यार", "मोहब्बत", "इश्क", "दिल", "तुमसे प्यार",
        # Russian native
        "я тебя люблю", "любовь", "люблю тебя", "милая", "дорогой",
        # Hindi transliterated
        "pyaar", "mohabbat", "ishq", "tujhse pyaar", "dilbar",
    ],
    "hype": [
        # English
        "hustle", "flex", "drip", "squad", "grind", "trap", "stackin", "stacking",
        "no cap", "on god", "run it up", "gettin money", "getting money",
        "we lit", "turn up", "finna", "bussin", "slatt", "gang gang",
        # Spanish
        "dinero", "poder", "fuego", "gana", "arriba", "fiesta", "flow",
        # French
        "argent", "pouvoir", "feu", "allez", "on lâche rien",
        # Portuguese
        "dinheiro", "poder", "fogo", "bora",
        # German
        "geld", "macht", "feuer", "komm hoch", "lass es krachen", "hoch",
        # Italian
        "soldi", "potere", "fuoco", "forza", "dai",
        # Dutch
        "geld", "macht", "vuur", "kom op", "energie",
        # Arabic transliterated
        "yalla", "wallah", "habba",
        # Arabic native
        "قوي", "انطلق", "يلا",
        # Korean transliterated
        "hwaiting", "bul", "kkeutnaebwa",
        # Korean native
        "파이팅", "신나", "최고야", "에너지",
        # Japanese native
        "頑張れ", "最高", "勝利", "元気", "強い",
        # Chinese native
        "加油", "最棒", "胜利", "勇敢",
        # Hindi native
        "जोश", "ताकत", "आगे बढ़ो",
        # Russian native
        "вперёд", "сила", "победа",
        # Hindi transliterated
        "josh", "jazba", "aag",
    ],
    "introspective": [
        # English
        "wondering", "searching my soul", "asking myself", "reflecting on",
        "looking back", "memories flood", "who am i", "what am i", "question everything",
        "lost myself", "finding myself", "inner peace", "meditation",
        # Spanish
        "reflexionar", "preguntarme", "alma", "recuerdos", "quién soy",
        "buscarme", "paz interior",
        # French
        "me demander", "réfléchir", "l'âme", "souvenirs", "qui suis-je",
        "chercher en moi",
        # Portuguese
        "refletir", "perguntar", "alma", "memórias", "quem sou eu",
        # German
        "nachdenken", "mich fragen", "seele", "erinnerungen", "wer bin ich",
        "in mich gehen",
        # Italian
        "riflettere", "chiedermi", "anima", "ricordi", "chi sono",
        # Dutch
        "nadenken", "mezelf afvragen", "ziel", "herinneringen", "wie ben ik",
    ],
    "euphoric": [
        # English
        "ecstasy", "euphoria", "paradise", "heaven on earth", "feeling alive",
        "on top of the world", "riding high", "blissful", "pure joy", "transcend",
        "free spirit", "soaring", "limitless", "unstoppable",
        # Spanish
        "éxtasis", "paraíso", "cielo", "libre", "alegría", "euforia", "felicidad",
        # French
        "extase", "paradis", "liberté", "joie", "bonheur", "euphorie",
        # Portuguese
        "êxtase", "paraíso", "liberdade", "alegria", "felicidade",
        # German
        "ekstase", "paradies", "freiheit", "freude", "glück", "unaufhaltbar",
        # Italian
        "estasi", "paradiso", "libertà", "gioia", "felicità",
        # Dutch
        "extase", "paradijs", "vrijheid", "vreugde", "geluk",
        # Korean transliterated
        "haengbok", "kibbeum",
        # Korean native
        "행복", "기쁨", "신나", "최고",
        # Japanese native
        "嬉しい", "楽しい", "幸せ", "最高", "喜び",
        # Chinese native
        "快乐", "幸福", "开心", "高兴", "欢乐",
        # Arabic native
        "سعيد", "فرحان", "سعادة",
        # Hindi native
        "खुशी", "आनंद", "मस्ती",
        # Russian native
        "счастье", "радость", "весело",
        # Hindi transliterated
        "khushi", "aanand", "masti",
    ],
    "dark": [
        # English
        "darkness", "shadow", "haunted", "devil", "evil spirit", "demonic",
        "death comes", "bleed out", "hollow inside", "void inside", "sinister",
        "damnation", "cursed", "nightmare", "abyss", "torment",
        # Spanish
        "oscuridad", "sombra", "diablo", "maldito", "muerte", "tormento",
        "tinieblas", "maldición",
        # French
        "obscurité", "ombre", "diable", "maudit", "mort", "tourment",
        "ténèbres", "malédiction",
        # Portuguese
        "escuridão", "sombra", "diabo", "maldito", "morte", "tormento",
        # German
        "dunkelheit", "schatten", "teufel", "verdammt", "albtraum", "qual",
        "finsternis", "verflucht",
        # Italian
        "oscurità", "ombra", "diavolo", "maledetto", "morte", "tormento",
        "tenebre", "incubo",
        # Dutch
        "duisternis", "schaduw", "duivel", "vervloekt", "dood", "kwelling",
        "nachtmerrie",
        # Japanese/anime transliterated
        "yami", "akuma", "shi no kage",
        # Japanese native
        "闇", "悪魔", "呪い", "死", "恐怖", "暗闇", "絶望", "地獄",
        # Chinese native
        "黑暗", "恶魔", "死亡", "诅咒", "绝望", "阴影",
        # Arabic native
        "ظلام", "شيطان", "لعنة", "موت", "عذاب",
        # Korean native
        "어둠", "악마", "죽음", "저주", "절망",
        # Hindi native
        "अंधेरा", "शैतान", "मृत्यु", "दर्द", "डर",
        # Russian native
        "темнота", "тьма", "дьявол", "смерть", "проклятие",
        # Arabic transliterated
        "zalam", "shaitan",
        # Hindi transliterated
        "andhera", "shaitan", "maut",
    ],
    "party": [
        # English
        "let's party", "on the dancefloor", "dance floor", "nightclub", "shots all night",
        "turn it up", "good times tonight", "everybody dance", "we came to party",
        # Spanish
        "fiesta", "bailar", "baila", "club", "toda la noche", "a bailar",
        # French
        "fête", "danser", "boîte de nuit", "on fait la fête",
        # Portuguese
        "festa", "dançar", "balada", "bora dançar",
        # Arabic transliterated
        "hafleh", "raqs", "yalla noos",
        # German
        "feiern", "tanzfläche", "lass uns tanzen", "auf die tanzfläche", "party machen",
        # Italian
        "festa", "ballare", "discoteca", "balliamo", "tutta la notte",
        # Dutch
        "feest", "dansen", "dansvloer", "nachtclub", "laten we dansen",
        # Korean transliterated
        "paati", "nolda", "chuda",
        # Korean native
        "파티", "신나게", "춤춰", "축제",
        # Japanese native
        "パーティー", "踊ろう", "祭り", "楽しもう",
        # Chinese native
        "派对", "跳舞", "庆祝", "狂欢",
        # Arabic native
        "حفلة", "ارقص", "نرقص",
        # Hindi native
        "नाचो", "मस्ती", "जश्न",
        # Russian native
        "вечеринка", "танцевать", "праздник",
        # Hindi transliterated
        "nacho", "masti", "jashn",
    ],

    # ── Thematic (lyric-first packs; feed lyr_* tags for scorer) ───────────────
    "goodbye": [
        # English
        "farewell", "walking away", "last time i", "never again", "leaving you",
        "i'm leaving", "moving on", "it's over", "waved goodbye", "end of us",
        "walk away", "gone for good", "final goodbye", "let you go", "letting go",
        "closed this chapter", "endings", "said our goodbyes", "one last time",
        # Multilingual
        "adiós for good", "auf wiedersehen", "addio per sempre", "tot ziens",
        "au revoir", "tchau", "xudaa haafiz",
    ],
    "homesick": [
        # English
        "hometown", "going home", "back home", "miss home", "miles from home",
        "where i grew up", "old neighborhood", "childhood home", "family back home",
        "missing home", "roots run deep", "small town", "road that leads home",
        # Multilingual
        "heim vermissen", "nostalgia di casa", "heimweh", "mal du pays",
        "saudade de casa",
    ],
    "nostalgic": [
        # English
        "remember when", "those days", "used to be", "way back when", "throwback",
        "memories of", "back then", "younger days", "old days", "miss those times",
        "golden days", "wish i could go back", "those summer nights",
        # Multilingual
        "tempos antigos", "époque révolue", "früher war", "los viejos tiempos",
        "bei no koro", "purane din",
    ],
    "hope": [
        # English
        "better days ahead", "hold on", "we'll be alright", "sun will rise",
        "brighter future", "still believe", "don't give up", "light at the end",
        "someday we will", "keep going", "not the end",
        # Spanish
        "mejores días", "seguir adelante", "no te rindas", "hay esperanza",
        # French
        "jours meilleurs", "tenir bon", "ne pas abandonner", "espoir",
        # Portuguese
        "dias melhores", "não desistir", "esperança", "vai melhorar",
        # German
        "nicht aufgeben", "bessere zeiten", "irgendwann", "es wird besser",
        "noch nicht fertig", "halte durch",
        # Italian
        "giorni migliori", "non arrendersi", "speranza", "andrà meglio",
        # Dutch
        "betere tijden", "niet opgeven", "hoop", "het wordt beter",
        # Hindi transliterated
        "umeed", "asha", "kal acha hoga",
    ],
    "struggle": [
        # English
        "broke and", "struggling", "pay the rent", "working double", "barely getting by",
        "empty pockets", "hard times", "tired of fighting", "keep my head up",
        # Multilingual
        "luchar", "lutter", "kämpfen", "lottare", "vechten", "sangharsh",
        "dificultades", "difficultés",
    ],
    "faith": [
        # English
        "i pray", "prayer", "amen", "lord i", "god will", "blessed", "give it to god",
        "saved my soul", "church on sunday", "hallelujah", "jesus",
        # Multilingual
        "rezar", "prier", "beten", "pregare", "bidden",
        "inshallah", "alhamdulillah", "mashallah",
        "bhagwan", "ishwar", "ram naam",
    ],
    "missing_you": [
        # English
        "wish you were here", "without you here", "thinking of you", "need you back",
        "come back to me", "read your messages", "still your side", "empty bed",
        "your side of", "ghost me", "left on read", "if you called",
        # Multilingual
        "te extraño", "manque", "saudade de você", "ich vermisse dich",
        "mi manchi", "ik mis jou", "tujhe yaad karta hoon",
    ],
    "revenge": [
        # English
        "payback", "karma coming", "you will regret", "remember this", "plotting on",
        "get even", "watch your back", "you did this", "no forgiveness",
        # Multilingual
        "venganza", "revanche", "rache", "vendetta", "wraak",
        "karma aayega", "badla lunga",
    ],
    "money": [
        # English
        "count the money", "count my money", "bankroll", "racks on", "bands on",
        "million dollars", "new whip", "cash out", "paid in full", "money long",
        "stack it up", "rich forever", "make it rain", "bag secured",
        # Multilingual
        "dinero", "argent", "grana", "soldi", "centen",
        "paisa", "ameer",
    ],
    "freedom": [
        # English
        "run away with", "running away", "break these chains", "no chains", "open highway",
        "windows down", "nowhere to be", "leave this town", "starting over",
        "free at last", "finally free", "no turning back", "border crossing",
        # Multilingual
        "libertad", "liberté", "freiheit", "libertà", "vrijheid",
        "azaadi", "mukti",
    ],
    "night_drive": [
        # English
        "dashboard lights", "city lights pass", "highway tonight", "3am on the",
        "empty road", "gas station glow", "rearview mirror", "neon blur",
        "driving nowhere", "passenger seat", "midnight miles",
        # Multilingual
        "conducir de noche", "conduire la nuit", "nächtliche fahrt",
        "guidare di notte", "rijden in de nacht",
    ],
    "family": [
        # English
        "mama", "momma", "mother", "father", "daddy", "dad", "family first",
        "my brother", "my sister", "grandma", "grandpa", "blood is thicker",
        "raised me", "my kids", "for my son", "for my daughter",
        # Spanish
        "mamá", "papá", "familia", "hermano", "hermana", "abuela", "abuelo",
        # French
        "maman", "papa", "famille", "frère", "sœur", "grand-mère", "grand-père",
        # Portuguese
        "mãe", "pai", "família", "irmão", "irmã", "avó", "avô",
        # German
        "mutter", "vater", "bruder", "schwester", "oma", "opa", "familie",
        "für meine kinder", "meine tochter", "mein sohn",
        # Italian
        "mamma", "papà", "famiglia", "fratello", "sorella", "nonna", "nonno",
        # Dutch
        "mama", "papa", "familie", "broer", "zus", "oma", "opa",
        # Arabic transliterated
        "yamma", "ummi", "abi", "akhoya", "okhti",
        # Arabic native
        "أمي", "أبي", "أخي", "أختي", "عائلة",
        # Hindi transliterated
        "maa", "baap", "bhai", "behan", "parivaar", "bachche",
        # Hindi native
        "माँ", "पापा", "भाई", "बहन", "परिवार",
        # Korean transliterated
        "eomma", "appa", "oppa", "unni",
        # Korean native
        "엄마", "아빠", "오빠", "언니", "가족",
        # Japanese native
        "お母さん", "お父さん", "家族", "兄弟", "姉妹",
        # Chinese native
        "妈妈", "爸爸", "家人", "兄弟", "姐妹", "父母",
        # Russian native
        "мама", "папа", "семья", "брат", "сестра",
    ],
    "friends": [
        # English
        "day one", "ride or die", "my homies", "my crew", "best friend",
        "through thick and thin", "we still here", "loyalty", "real ones",
        # Spanish
        "amigos", "mi gente", "mejor amigo", "lealtad", "siempre juntos",
        # French
        "amis", "meilleur ami", "loyauté", "ensemble toujours",
        # Portuguese
        "amigos", "meu amigo", "lealdade", "juntos sempre",
        # German
        "bester freund", "loyalität", "durch dick und dünn", "meine crew",
        "wir sind dabei", "zusammen",
        # Italian
        "amici", "migliore amico", "lealtà", "sempre insieme",
        # Dutch
        "vrienden", "beste vriend", "loyaliteit", "samen",
        # Hindi transliterated
        "dost", "yaar", "dosti", "saath milke",
        # Hindi native
        "दोस्त", "यार", "दोस्ती", "साथ",
        # Korean native
        "친구", "우리", "함께", "의리",
        # Japanese native
        "友達", "仲間", "絆", "一緒に",
        # Chinese native
        "朋友", "兄弟", "姐妹", "在一起", "友情",
        # Arabic native
        "صديق", "صديقة", "رفيق", "معاً",
        # Russian native
        "друзья", "вместе", "дружба",
    ],
    "jealousy": [
        # English
        "jealous of", "green with envy", "you with her", "you with him",
        "watching you", "can't stand to see", "territory", "possessive",
        # Multilingual
        "celoso", "jaloux", "eifersüchtig", "geloso", "jaloers",
        "jalan", "jadiya",
    ],
    "summer": [
        # English
        "summer nights", "june", "july", "august heat", "pool party",
        "sun on my skin", "vacation", "beach with", "top down summer",
        # Spanish
        "verano", "playa", "bajo el sol", "vacaciones", "noche de verano",
        # French
        "été", "plage", "au soleil", "vacances", "nuit d'été",
        # Portuguese
        "verão", "praia", "ao sol", "férias", "noite de verão",
        # German
        "sommernacht", "sommerabend", "am strand", "im sommer", "juli",
        # Italian
        "estate", "spiaggia", "sole", "vacanze", "notte d'estate",
        # Dutch
        "zomer", "strand", "in de zon", "vakantie", "zomernacht",
        # Hindi transliterated
        "garmiyan", "samundar", "dhoop",
    ],
    "city": [
        # English
        "downtown", "skyline", "subway", "concrete jungle", "city never sleeps",
        "block", "corner store", "penthouse", "traffic lights",
        # Spanish
        "ciudad", "calles", "barrio", "rascacielos", "metrópolis",
        # French
        "ville", "dans la rue", "quartier", "gratte-ciel", "métropole",
        # Portuguese
        "cidade", "ruas", "bairro", "arranha-céu",
        # German
        "innenstadt", "beton", "hochhaus", "stadtleben", "neonlichter",
        # Italian
        "città", "strade", "quartiere", "grattacielo",
        # Dutch
        "stad", "straat", "wijk", "wolkenkrabber",
        # Arabic transliterated
        "madina", "shaware",
        # Hindi transliterated
        "sheher", "galliyan", "sadak",
    ],
    "ocean": [
        # English
        "ocean waves", "tide", "sail away", "anchor", "deep blue", "underwater",
        "shore", "island", "pirate",
        # Multilingual
        "océano", "bord de la mer", "aan de zee", "oceano", "op zee",
        "samundar", "dariya",
    ],
}


# ── Lyrics preprocessing ──────────────────────────────────────────────────────

# Negation words that flip a keyword hit to a miss.
# Latin-only; we don't have robust negation lists for every script.
_NEGATION_RE = re.compile(
    r"\b(not|no|never|nobody|nothing|neither|nor|none|without|"
    r"cannot|can't|won't|don't|doesn't|didn't|isn't|wasn't|weren't|"
    r"haven't|hasn't|hadn't|shouldn't|wouldn't|couldn't|"
    r"hardly|barely|scarcely|far from|anything but)\b",
    re.IGNORECASE,
)

# How many characters to look back before a keyword for a negation word.
# 40 chars covers ~5 short words ("I am not feeling so"), which is safe.
_NEGATION_WINDOW = 40


def _deduplicate_stanzas(text: str) -> str:
    """
    Remove repeated stanzas before analysis so the chorus (repeated 3-4x)
    doesn't triple-count its keywords.

    Splits on blank lines, normalises whitespace per stanza, keeps only the
    FIRST occurrence of each unique stanza.  Identical or near-identical
    stanzas (same normalised text) are collapsed to one.
    """
    stanzas = re.split(r"\n{2,}", text.strip())
    seen: set[str] = set()
    unique: list[str] = []
    for stanza in stanzas:
        key = re.sub(r"\s+", " ", stanza.strip().lower())
        if key and key not in seen:
            seen.add(key)
            unique.append(stanza.strip())
    return "\n\n".join(unique)


def _count_keyword_hits(text: str, keyword: str) -> int:
    """
    Count occurrences of `keyword` in `text` that are NOT preceded by a
    negation word within the same sentence clause.

    The negation window is capped at _NEGATION_WINDOW chars AND clipped to
    the most recent sentence boundary (. ! ? ; newline) so that negations
    from earlier sentences don't bleed into later ones.

    Examples:
      "I'm so sad"                    → sad → 1 hit
      "I'm not sad anymore"           → sad → 0 hits  (negated)
      "never felt so happy"           → happy → 0 hits  (negated)
      "I never felt sad. I am happy"  → sad → 0, happy → 1  (boundary respected)
      "the sadness never leaves"      → sadness → 1 (negation is AFTER keyword)
    """
    hits = 0
    kw_len = len(keyword)
    search_start = 0
    while True:
        idx = text.find(keyword, search_start)
        if idx == -1:
            break
        prefix_raw = text[max(0, idx - _NEGATION_WINDOW) : idx]
        # Clip to the last sentence-ending punctuation or newline so negations
        # from a prior sentence don't affect this keyword.
        last_boundary = max(
            prefix_raw.rfind("."),
            prefix_raw.rfind("!"),
            prefix_raw.rfind("?"),
            prefix_raw.rfind(";"),
            prefix_raw.rfind("\n"),
        )
        prefix = prefix_raw[last_boundary + 1:] if last_boundary >= 0 else prefix_raw
        if not _NEGATION_RE.search(prefix):
            hits += 1
        search_start = idx + kw_len
    return hits


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

    # ── Step 1: de-duplicate repeated stanzas (chorus, bridge) ───────────────
    # Prevents the chorus being counted 3-4x and dominating the score.
    deduped  = _deduplicate_stanzas(lyrics)
    text     = deduped.lower()

    # ── Step 2: tokenise for word_count (all scripts) ────────────────────────
    words = re.findall(
        r"[a-záéíóúàâãêôõçüñäöß'èìòùœæøå"
        r"\u0600-\u06FF"          # Arabic
        r"\uAC00-\uD7FF"          # Korean Hangul syllables
        r"\u1100-\u11FF"          # Hangul Jamo
        r"\u3130-\u318F"          # Hangul Compatibility Jamo
        r"\u0900-\u097F"          # Devanagari (Hindi)
        r"\u4E00-\u9FFF"          # CJK Unified Ideographs (Chinese/Japanese Kanji)
        r"\u3040-\u30FF"          # Hiragana + Katakana
        r"\u0400-\u04FF"          # Cyrillic (Russian)
        r"\u0E00-\u0E7F"          # Thai
        r"]+",
        text,
    )

    # ── Step 3: negation-aware keyword scoring ────────────────────────────────
    # _count_keyword_hits() skips hits where a negation word appears within
    # _NEGATION_WINDOW chars before the keyword.
    # Denominator capped at 60 so expanding language lists doesn't dilute scores.
    mood_scores: dict[str, float] = {}
    for mood, keywords in MOOD_KEYWORDS.items():
        hits = sum(_count_keyword_hits(text, kw) for kw in keywords)
        if hits:
            _denom = min(len(keywords), 60)
            mood_scores[mood] = round(min(hits / max(_denom, 1), 1.0), 4)

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
    # Require score > 0.04 to filter single-keyword false positives from
    # large multilingual lists (1 hit / 40 keywords ≈ 0.025, below threshold).
    # Thematic moods with small keyword lists (ocean ~15) still pass on 1 hit.
    return {f"lyr_{mood}": score for mood, score in scores.items() if score > 0.03}


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
