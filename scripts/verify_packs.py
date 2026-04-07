"""Quick verification of M1.0 packs.json changes."""
import json, os
path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "packs.json")
with open(path, encoding="utf-8") as f:
    d = json.load(f)
m = d["moods"]
checks = [
    ("Heartbreak",         ["angry", "emotional"]),
    ("Emo Hour",           ["angry", "emotional"]),
    ("Raw Emotion",        ["angry", "emotional"]),
    ("Punk Sprint",        ["angry"]),
    ("Rage Lift",          ["hype"]),
    ("Anime OST Energy",   ["hype", "emotional"]),
    ("Anime Openings",     ["hype"]),
    ("Rainy Window",       ["melancholic", "introspective"]),
    ("Overthinking",       ["melancholic"]),
    ("Goth / Darkwave",    ["melancholic"]),
    ("Sundown",            ["melancholic", "introspective"]),
    ("Acoustic Corner",    ["melancholic", "introspective"]),
    ("Heartbreak",         ["angry"]),
]
all_ok = True
for mood, should_not_have in checks:
    if mood not in m:
        print(f"MISSING MOOD: {mood}")
        all_ok = False
        continue
    tags = m[mood]["expected_tags"]
    found = [t for t in should_not_have if t in tags]
    if found:
        print(f"FAIL  {mood}: still has {found}")
        all_ok = False
    else:
        print(f"OK    {mood}")

# Also confirm angry stays where it belongs
keep_angry = ["Villain Arc", "Adrenaline", "Rage Lift", "Drill", "Hard Reset"]
for mood in keep_angry:
    if mood not in m:
        continue
    tags = m[mood].get("expected_tags", []) + m[mood].get("semantic_core", [])
    has = "angry" in tags
    print(f"{'OK' if has else 'WARN'} {mood}: angry={'present' if has else 'MISSING'}")

print("\nAll OK" if all_ok else "\nSome checks FAILED")
