"""
M1.0 — packs.json mood audit script.
Removes cross-contaminating expected_tags from 30 moods.
Run once, commit, then delete.
"""
import json
import os

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "packs.json")

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

moods = data["moods"]

# {mood_name: [tags_to_remove_from_expected_tags]}
# Rule 1: "angry" removed from moods where anger is not defining
# Rule 2: "hype" removed where party/celebration is not core
# Rule 3: "melancholic" removed where mood is not sad/sorrowful
# Rule 4: "introspective" removed where it duplicates semantic_core
# Rule 5: "emotional" removed everywhere (too vague, zero discrimination)
REMOVALS = {
    "Acoustic Corner":          ["melancholic", "introspective"],
    "Anime Endings":            ["melancholic", "emotional"],
    "Anime OST Energy":         ["hype", "emotional"],
    "Anime Openings":           ["hype"],
    "Brass & Drumline Energy":  ["hype"],
    "Cloud Rap Haze":           ["introspective"],
    "Country Roads":            ["introspective"],
    "Dark Pop":                 ["introspective"],
    "Emo Hour":                 ["angry", "emotional"],
    "Flex Tape":                ["hype"],
    "Goth / Darkwave":          ["melancholic"],
    "Healing Kind":             ["emotional"],
    "Heartbreak":               ["angry", "emotional"],
    "Hyperpop":                 ["hype"],
    "Hyperpop Emotional Crash": ["emotional"],
    "Indie Bedroom":            ["introspective"],
    "Jazz Nights":              ["introspective"],
    "Kawaii Metal Sparkle":     ["hype"],
    "Neo-Soul":                 ["introspective"],
    "Nostalgia":                ["introspective"],
    "Overthinking":             ["melancholic"],
    "Psychedelic":              ["introspective"],
    "Punk Sprint":              ["angry"],
    "Rage Lift":                ["hype"],
    "Rainy Window":             ["melancholic", "introspective"],
    "Raw Emotion":              ["angry", "emotional"],
    "Smoke & Mirrors":          ["introspective"],
    "Sundown":                  ["melancholic", "introspective"],
}

applied = []
not_found = []
no_change = []

for mood_name, tags_to_remove in REMOVALS.items():
    if mood_name not in moods:
        not_found.append(mood_name)
        continue
    original = moods[mood_name].get("expected_tags", [])
    remove_set = set(tags_to_remove)
    updated = [t for t in original if t not in remove_set]
    actually_removed = [t for t in tags_to_remove if t in original]
    if actually_removed:
        moods[mood_name]["expected_tags"] = updated
        applied.append((mood_name, actually_removed))
    else:
        no_change.append(mood_name)

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"M1.0 packs.json audit complete — {len(applied)} moods updated\n")
for mood_name, removed in applied:
    print(f"  {mood_name}: removed {removed}")
if no_change:
    print(f"\nNo-op (tags not present): {no_change}")
if not_found:
    print(f"\nMOOD NOT FOUND: {not_found}")
