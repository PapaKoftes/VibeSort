# Contributing to Vibesort

Thanks for wanting to make Vibesort better! There are several ways to contribute — no coding required for most of them.

---

## No-Code Contributions

### Submit Mood Anchors

Anchors are the seed tracks that define each mood pack. More anchors = better scoring coverage. This is the single highest-impact contribution you can make.

**How to submit:**

1. Open `data/mood_anchors.json`
2. Find the mood you want to improve (e.g. `"rainy_day"`, `"late_night_drive"`)
3. Add Spotify track URIs that **unambiguously** belong to that mood

**Rules for good anchors:**

- The track must be a clear, obvious example of the mood — if you'd have to explain why it fits, it probably doesn't
- Avoid tracks that equally belong to multiple conflicting moods (e.g. a song that's both "hype" and "peaceful")
- Use the Spotify URI format: `spotify:track:TRACK_ID` (find it in Spotify → share → Copy Song Link, then extract the ID)
- Aim for diversity: different artists, eras, and sub-genres within the mood

**Example:**
```json
"rainy_day": [
  "spotify:track:4aebBr4JAihzJQR0CiIZJv",
  "spotify:track:3HfB5hBU0dmBt8T0iCmFCI"
]
```

Open a pull request with your additions. Include a one-line note on why each track fits.

---

### Report Miscategorised Tracks

If a track appears in a mood playlist where it clearly doesn't belong, open an issue:

1. Go to [Issues](https://github.com/PapaKoftes/VibeSort/issues) → **New Issue**
2. Use the title: `[Misfire] Artist - Track → Mood`
3. Include: why you think it's wrong, which mood it should be in instead (if any)

This helps us tune the conflict rules and anchor set.

---

### Suggest New Mood Packs

Vibesort currently has 110 mood packs. If you have a clear vision for a new one:

1. Open an issue titled `[New Mood] Your Mood Name`
2. Describe the vibe in 2–3 sentences
3. List 5–10 seed tracks (artist + title is fine)
4. Suggest what existing moods it should be similar to or distinct from

A new mood pack needs: a slug, a display name, 8+ expected tags, and 6+ anchors. We'll handle the implementation.

---

### Improve Mood Definitions (`data/packs.json`)

Each mood pack has `expected_tags`, `vibe_sentence`, and `preferred_macro_genres`. If a mood feels off:

- Check its `expected_tags` — are they accurate?
- Check its `preferred_macro_genres` — does the genre list make sense?
- Submit a PR with your corrections and a brief explanation

---

## Code Contributions

### Setup

```bash
git clone https://github.com/PapaKoftes/VibeSort.git
cd VibeSort
pip install -r requirements.txt
cp .env.example .env   # add your Spotify credentials
streamlit run app.py
```

### Run the validator

Before submitting a PR, run:

```bash
python scripts/validate_all.py
```

It should report 0 FAIL. Warnings are acceptable if you explain them in the PR description.

### Pull Request Guidelines

- Keep PRs focused: one feature or fix per PR
- Include a brief description of what changed and why
- If you're adding a new enrichment source, add a corresponding entry to `data/cache/` and document the cache key in `docs/ROADMAP.md`
- If you're changing scoring weights, include before/after playlist size stats (run a scan with `scripts/validate_all.py --coverage`)

---

## Anchor Submission Checklist

Before submitting anchor additions, verify:

- [ ] Each URI resolves to a real Spotify track (paste into Spotify to confirm)
- [ ] The track is unambiguously associated with the target mood
- [ ] You haven't added the same URI to two conflicting moods (e.g. `sleep` and `hype`)
- [ ] The mood now has ≥ 8 anchors total after your addition
- [ ] Run `python scripts/validate_all.py` — no new FAILs

---

## Questions?

Open an issue or start a Discussion at [github.com/PapaKoftes/VibeSort](https://github.com/PapaKoftes/VibeSort). We're friendly.
