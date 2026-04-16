"""
scripts/patch_macro_genres_international.py

Add international genre rules to data/macro_genres.json.
Covers French Rap, Arabic/MENA, German, Brazilian, Turkish, Hindi,
Italian, Russian, Spanish-language rock, and other regional markets.
Idempotent — re-running adds 0 duplicates.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "macro_genres.json")

with open(PATH, encoding="utf-8") as f:
    mg = json.load(f)

rules = mg["rules"]
existing = {r[0].lower() for r in rules if isinstance(r, list)}
print(f"Current rules: {len(rules)}")

NEW_RULES = [
    # ── French Rap
    ["rap français",             "French Rap"],
    ["rap francais",             "French Rap"],
    ["french rap",               "French Rap"],
    ["french trap",              "French Rap"],
    ["french hip hop",           "French Rap"],
    ["rap fr",                   "French Rap"],
    ["trap fr",                  "French Rap"],
    ["drill français",           "French Rap"],
    ["drill francais",           "French Rap"],
    ["rap belge",                "French Rap"],
    ["rap suisse",               "French Rap"],
    ["rap québécois",            "French Rap"],
    ["cloud rap français",       "French Rap"],
    ["trap francophone",         "French Rap"],
    ["rap africain",             "French Rap"],

    # ── Arabic / MENA
    ["arabic rap",               "World / Regional"],
    ["arabic trap",              "World / Regional"],
    ["arabic hip hop",           "World / Regional"],
    ["trap arabe",               "World / Regional"],
    ["rap arabe",                "World / Regional"],
    ["egyptian rap",             "World / Regional"],
    ["egyptian trap",            "World / Regional"],
    ["arabic drill",             "World / Regional"],
    ["levant rap",               "World / Regional"],
    ["gulf rap",                 "World / Regional"],
    ["khaleeji",                 "World / Regional"],
    ["moroccan rap",             "World / Regional"],
    ["algerian rap",             "World / Regional"],
    ["tunisian rap",             "World / Regional"],
    ["mena trap",                "World / Regional"],
    ["arab phonk",               "World / Regional"],
    ["arabic phonk",             "World / Regional"],

    # ── German Rap
    ["deutschrap",               "World / Regional"],
    ["german rap",               "World / Regional"],
    ["german trap",              "World / Regional"],
    ["german hip hop",           "World / Regional"],
    ["austrian rap",             "World / Regional"],
    ["swiss rap",                "World / Regional"],
    ["deutschtrap",              "World / Regional"],
    ["berlin rap",               "World / Regional"],
    ["österreichischer rap",     "World / Regional"],

    # ── Brazilian / Funk Carioca
    ["funk carioca",             "Brazilian / Funk Carioca"],
    ["funk brasileiro",          "Brazilian / Funk Carioca"],
    ["baile funk",               "Brazilian / Funk Carioca"],
    ["funk ostentação",          "Brazilian / Funk Carioca"],
    ["funk ostentacao",          "Brazilian / Funk Carioca"],
    ["funk melody",              "Brazilian / Funk Carioca"],
    ["funk 150 bpm",             "Brazilian / Funk Carioca"],
    ["brega funk",               "Brazilian / Funk Carioca"],
    ["piseiro",                  "Brazilian / Funk Carioca"],
    ["sertanejo",                "Brazilian / Funk Carioca"],
    ["pagode",                   "Brazilian / Funk Carioca"],
    ["forró",                    "Brazilian / Funk Carioca"],
    ["forro",                    "Brazilian / Funk Carioca"],
    ["axé",                      "Brazilian / Funk Carioca"],
    ["axe",                      "Brazilian / Funk Carioca"],

    # ── Brazilian Phonk / Trap
    ["phonk brasileiro",         "Brazilian Phonk"],
    ["brazilian phonk",          "Brazilian Phonk"],
    ["trap brasileiro",          "Brazilian Phonk"],
    ["trap br",                  "Brazilian Phonk"],
    ["rap nacional",             "Brazilian Phonk"],
    ["trap nacional",            "Brazilian Phonk"],

    # ── Turkish
    ["turkish rap",              "World / Regional"],
    ["türkçe rap",               "World / Regional"],
    ["turkce rap",               "World / Regional"],
    ["turkish trap",             "World / Regional"],
    ["türkçe trap",              "World / Regional"],
    ["turkish hip hop",          "World / Regional"],
    ["anatolian rock",           "World / Regional"],
    ["türk hip hop",             "World / Regional"],
    ["arabesk rap",              "World / Regional"],
    ["türkçe phonk",             "World / Regional"],

    # ── Hindi / South Asian
    ["hindi rap",                "World / Regional"],
    ["desi hip hop",             "World / Regional"],
    ["desi trap",                "World / Regional"],
    ["indian hip hop",           "World / Regional"],
    ["bollywood rap",            "World / Regional"],
    ["punjabi rap",              "World / Regional"],
    ["punjabi trap",             "World / Regional"],
    ["hindi trap",               "World / Regional"],
    ["mumbai rap",               "World / Regional"],
    ["south asian hip hop",      "World / Regional"],
    ["gully rap",                "World / Regional"],
    ["filmi",                    "World / Regional"],
    ["bollywood",                "World / Regional"],
    ["tollywood",                "World / Regional"],

    # ── Italian
    ["trap italiano",            "World / Regional"],
    ["italian trap",             "World / Regional"],
    ["rap italiano",             "World / Regional"],
    ["italian hip hop",          "World / Regional"],
    ["italian rap",              "World / Regional"],
    ["trap italiana",            "World / Regional"],
    ["cloud rap italiano",       "World / Regional"],
    ["musica italiana",          "World / Regional"],

    # ── Russian / Slavic
    ["russian rap",              "World / Regional"],
    ["russian hip hop",          "World / Regional"],
    ["russian trap",             "World / Regional"],
    ["post-soviet rap",          "World / Regional"],
    ["cis rap",                  "World / Regional"],
    ["russian phonk",            "World / Regional"],
    ["slavic rap",               "World / Regional"],
    ["russian pop",              "World / Regional"],

    # ── Spanish-language rock / Latin Alternative
    ["rock en español",          "Rock"],
    ["rock en espanol",          "Rock"],
    ["latin rock",               "Rock"],
    ["latin alternative",        "Indie / Alternative"],
    ["spanish language rock",    "Rock"],
    ["mexican rock",             "Rock"],
    ["argentinian rock",         "Rock"],
    ["chilean rock",             "Rock"],
    ["cumbia rock",              "Rock"],
    ["rock latinoamericano",     "Rock"],
    ["nueva canción",            "Folk / Americana"],
    ["nueva cancion",            "Folk / Americana"],

    # ── UK Afroswing
    ["afroswing",                "UK Rap / Grime"],
    ["uk afroswing",             "UK Rap / Grime"],

    # ── Other regional
    ["nigerian rap",             "World / Regional"],
    ["naija rap",                "World / Regional"],
    ["south african hip hop",    "World / Regional"],
    ["swedish rap",              "World / Regional"],
    ["swedish trap",             "World / Regional"],
    ["nordic rap",               "World / Regional"],
    ["dutch rap",                "World / Regional"],
    ["belgian rap",              "World / Regional"],
    ["greek rap",                "World / Regional"],
    ["polish rap",               "World / Regional"],
    ["czech rap",                "World / Regional"],
    ["romanian rap",             "World / Regional"],
    ["balkan rap",               "World / Regional"],
    ["persian rap",              "World / Regional"],
    ["iranian rap",              "World / Regional"],
    ["vietnamese rap",           "World / Regional"],
    ["thai trap",                "World / Regional"],
    ["thai rap",                 "World / Regional"],
    ["filipino rap",             "World / Regional"],
    ["opm",                      "World / Regional"],
    ["indonesian pop",           "World / Regional"],
    ["malay pop",                "World / Regional"],
    ["chinese rap",              "World / Regional"],
    ["mandopop",                 "K-Pop / J-Pop"],
    ["cantopop",                 "K-Pop / J-Pop"],
    ["chinese trap",             "World / Regional"],
    ["cpop",                     "K-Pop / J-Pop"],
    ["c-pop",                    "K-Pop / J-Pop"],
    ["taiwanese pop",            "K-Pop / J-Pop"],
    ["taiwanese rap",            "K-Pop / J-Pop"],
    ["vietnamese pop",           "World / Regional"],
    ["thai pop",                 "World / Regional"],
]

added = 0
by_macro: dict[str, int] = {}
for rule in NEW_RULES:
    raw, macro = rule[0], rule[1]
    if raw.lower() not in existing:
        rules.append(rule)
        existing.add(raw.lower())
        by_macro[macro] = by_macro.get(macro, 0) + 1
        added += 1

mg["rules"] = rules
with open(PATH, "w", encoding="utf-8") as f:
    json.dump(mg, f, ensure_ascii=False, indent=2)

# Verify
with open(PATH, encoding="utf-8") as f:
    verify = json.load(f)
print(f"Added {added} international genre rules")
print(f"Total rules now: {len(verify['rules'])}")
print("\nBy macro genre:")
for macro, count in sorted(by_macro.items(), key=lambda x: -x[1]):
    print(f"  {macro:<35} +{count}")
print("\nJSON valid: OK")
