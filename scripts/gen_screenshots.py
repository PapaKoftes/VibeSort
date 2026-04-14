"""Generate demo screenshots and GIF from snapshot data."""
import json, matplotlib.pyplot as plt, matplotlib.patches as mpatches
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw

snap = json.load(open("outputs/.last_scan_snapshot.json", encoding="utf-8"))
mood_results = snap["mood_results"]
OUT = Path("docs/screenshots")
OUT.mkdir(exist_ok=True)

# ── 1. Fix Mood Atlas ─────────────────────────────────────────────────────────
sorted_moods = sorted(mood_results.items(), key=lambda x: -x[1].get("count", 0))[:30]
labels = [m for m,_ in sorted_moods]
counts = [info.get("count",0) for _,info in sorted_moods]
colors = ["#6366f1" if c>=30 else "#818cf8" if c>=25 else "#a78bfa" if c>=20 else "#c4b5fd" for c in counts]

fig, ax = plt.subplots(figsize=(16, 6))
fig.patch.set_facecolor("#0e1117")
ax.set_facecolor("#0e1117")
x = np.arange(len(labels))
bars = ax.bar(x, counts, color=colors, width=0.7, edgecolor="#0e1117", linewidth=0.5)
for bar, cnt in zip(bars, counts):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.3, str(cnt),
            ha="center", va="bottom", color="white", fontsize=8, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=45, ha="right", color="white", fontsize=9.5)
ax.tick_params(axis="y", colors="#9ca3af", labelsize=9)
ax.set_ylabel("tracks in playlist", color="#9ca3af", fontsize=10)
ax.spines[:].set_visible(False)
ax.set_ylim(0, max(counts)*1.15)
legend = [
    mpatches.Patch(color="#6366f1", label="30+ tracks"),
    mpatches.Patch(color="#818cf8", label="25-29 tracks"),
    mpatches.Patch(color="#a78bfa", label="20-24 tracks"),
    mpatches.Patch(color="#c4b5fd", label="<20 tracks"),
]
ax.legend(handles=legend, facecolor="#1a1a2e", edgecolor="#333", labelcolor="white", fontsize=9, loc="upper right")
fig.suptitle("Mood Atlas -- Your Top 30 Vibes", color="white", fontsize=14, fontweight="bold", y=1.0)
plt.tight_layout()
plt.savefig(OUT/"mood_atlas.png", dpi=150, bbox_inches="tight", facecolor="#0e1117")
plt.close()
print("mood_atlas.png done")

# ── 2. Demo GIF frames (PIL) ──────────────────────────────────────────────────
W, H = 1200, 700
BG    = (14, 17, 23)
ACCENT = (99, 102, 241)
GREEN  = (34, 197, 94)
TEXT   = (255, 255, 255)
MUTED  = (156, 163, 175)
CARD   = (22, 27, 34)
PURPLE = (167, 139, 250)
DARK_CARD = (21, 27, 38)


def header(img, d, title, subtitle):
    d.rectangle([0, 0, W, 52], fill=(18, 22, 30))
    d.text((20, 16), "Vibesort", fill=TEXT)
    d.text((W-130, 16), "localhost:8501", fill=MUTED)
    d.text((60, 68), title, fill=TEXT)
    d.text((60, 92), subtitle, fill=MUTED)
    d.line([60, 118, W-60, 118], fill=(40, 45, 55), width=1)


def frame_home():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(img, d, "Your Library Dashboard", "After scan -- here's what Vibesort found")
    stats = [("2,620","Tracks"), ("85","Moods"), ("12","Genres"), ("487","Artists")]
    for i, (val, lbl) in enumerate(stats):
        x = 60 + i*240
        d.rectangle([x, 138, x+200, 220], fill=CARD)
        d.text((x+20, 148), val, fill=TEXT)
        d.text((x+20, 175), lbl, fill=MUTED)
    d.rectangle([60, 238, 920, 282], fill=(21, 47, 30))
    d.text((80, 252), "Start here:  Bedroom Pop Diary  --  36 tracks  *  Perfect fit", fill=GREEN)
    d.rectangle([930, 238, 1100, 282], fill=ACCENT)
    d.text((970, 252), "Open it", fill=TEXT)
    d.text((60, 308), "Your Library's Emotional Fingerprint", fill=TEXT)
    d.rectangle([60, 334, 1100, 370], fill=DARK_CARD)
    d.text((80, 348), "Your library leans heavily into Power / Energy -- Hard Reset, Villain Arc cover 310 tracks.", fill=MUTED)
    bars_data = [("Power / Energy", 0.26, (239,68,68)), ("Party / Dance", 0.22, (245,158,11)),
                 ("Chill / Focus", 0.18, (34,197,94)), ("Dark", 0.17, ACCENT), ("Story", 0.17, PURPLE)]
    for i, (lbl, pct, col) in enumerate(bars_data):
        y = 388 + i*44
        bw = int(660*pct)
        d.rectangle([60, y, 60+bw, y+30], fill=col)
        d.rectangle([60+bw, y, 720, y+30], fill=(40,45,55))
        d.text((730, y+8), f"{lbl}  {round(pct*100)}%  ({round(pct*1176)} tracks)", fill=TEXT)
    return img


def frame_vibes():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(img, d, "Your Vibes", "85 mood playlists sorted by fit quality")
    d.text((60, 128), "85 moods found in your library", fill=MUTED)
    moods = [
        ("Hollow", "22 tracks", "Great fit", 0.78),
        ("Villain Arc", "19 tracks", "Good fit", 0.65),
        ("Late Night Drive", "28 tracks", "Great fit", 0.80),
        ("Bedroom Pop Diary", "36 tracks", "Perfect fit", 0.92),
        ("Hard Reset", "26 tracks", "Good fit", 0.70),
        ("Phonk Season", "24 tracks", "Good fit", 0.68),
    ]
    for i, (name, count, fit, coh) in enumerate(moods):
        col = i % 3
        row = i // 3
        x = 60 + col*375
        y = 155 + row*215
        d.rectangle([x, y, x+350, y+200], fill=CARD)
        d.text((x+14, y+14), name, fill=TEXT)
        d.text((x+14, y+36), f"{count}  *  match quality: {fit}", fill=MUTED)
        bw = int(320 * coh)
        d.rectangle([x+14, y+62, x+14+bw, y+74], fill=ACCENT)
        d.rectangle([x+14+bw, y+62, x+334, y+74], fill=(40,45,55))
        d.rectangle([x+14, y+162, x+334, y+188], fill=ACCENT)
        d.text((x+110, y+169), "Build Playlist", fill=TEXT)
    return img


def frame_badges():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(img, d, "Track Signal Badges", "Every track shows why it belongs here")
    d.rectangle([60, 130, 1100, 660], fill=CARD)
    d.text((78, 142), "Hollow  --  Full Tracklist (22 tracks)", fill=TEXT)
    d.line([78, 168, 1082, 168], fill=(40,45,55), width=1)
    d.text((78, 178), "3 tracks here are something you clearly return to.   11 found by mapping how your songs relate to each other.", fill=MUTED)
    d.text((78, 198), "Signal key:  [Anchor] = curated  [Personal] = you play this a lot  [Similar] = neighbour  [Last.fm] = crowd tags  [Lyrics] = lyric analysis", fill=(107,114,128))
    d.line([78, 218, 1082, 218], fill=(40,45,55), width=1)
    tracks = [
        ("How", "The Neighbourhood", "[Anchor]  [Personal]  [Last.fm]", "Alternative Rock"),
        ("Hallelujah", "Jeff Buckley", "[Anchor]  [Lyrics: sad]", "Folk Rock"),
        ("My Iron Lung", "Radiohead", "[Anchor]  [Similar]", "Alternative"),
        ("Devil Town", "Cavetown", "[Personal]  [Lyrics: sad]  [Late Night]", "Bedroom Pop"),
        ("Skinny Love", "Bon Iver", "[Similar]  [Last.fm]  [Lyrics: lonely]", "Indie Folk"),
        ("Scar Tissue", "Red Hot Chili Peppers", "[Similar]", "Alternative Rock"),
        ("Supermassive Black Hole", "Muse", "[Similar]  [Last.fm]", "Alt Rock"),
    ]
    for i, (name, artist, badges, genre) in enumerate(tracks):
        y = 234 + i*56
        d.text((95, y), name, fill=TEXT)
        d.text((95, y+20), artist, fill=MUTED)
        d.text((380, y+6), badges, fill=PURPLE)
        d.text((960, y+6), genre, fill=(75,85,99))
    return img


def frame_atlas():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(img, d, "Mood Atlas", "See all 87 moods -- strong, present, thin, or missing")
    d.text((60, 128), "87 total moods  *  85 found  *  2 unexplored", fill=MUTED)
    sections = [
        ("STRONG (30+ tracks)", (99,102,241), ["Bedroom Pop Diary (36)", "Neo-Soul (35)", "Metal Testimony (32)", "Queer Dance Confetti (32)", "Symphonic Metal (31)"]),
        ("PRESENT (20-29 tracks)", (129,140,248), ["Late Night Drive (28)", "Rainy Window (27)", "Old School Hip-Hop (27)", "Hollow (22)", "Villain Arc (19)"]),
        ("THIN (<20 tracks)", (196,181,253), ["K-Pop Zone (19)", "Drill (19)", "Adrenaline (20)", "Afterparty (20)"]),
        ("MISSING -- discovery gaps", (75,85,99), ["Kawaii Metal Sparkle", "Amapiano Sunset"]),
    ]
    y = 150
    for label, col, items in sections:
        d.rectangle([60, y, 86, y+22], fill=col)
        d.text((96, y+4), label, fill=TEXT)
        y += 28
        for item in items:
            d.text((100, y), item, fill=MUTED)
            y += 22
        y += 12
    # Discovery gap box
    d.rectangle([60, 560, 1100, 640], fill=DARK_CARD)
    d.text((80, 572), "Discovery Gaps -- add these tracks to unlock missing vibes:", fill=PURPLE)
    d.text((80, 596), "Kawaii Metal Sparkle: try  BABYMETAL - Gimme Choco!!  or  BABYMETAL - Karate", fill=MUTED)
    d.text((80, 618), "Amapiano Sunset: try  Kabza De Small - Sponono  or  Focalistic - Ke Star", fill=MUTED)
    return img


def frame_deploy():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(img, d, "Deploy to Spotify", "Queue playlists, rename them, push in one click")
    steps = [
        ("1", "Connect to Spotify", GREEN, "OAuth in your browser -- 30 seconds"),
        ("2", "Scan your library", GREEN, "3-10 min first time. Cached after that."),
        ("3", "Browse 85 mood playlists", GREEN, "Sorted by fit quality. Badges explain every track."),
        ("4", "Build + queue playlists", (245,158,11), "Name them. Preview tracks. Toggle Spotify recommendations."),
        ("5", "Deploy to Spotify", ACCENT, "One click. All queued playlists created instantly."),
    ]
    for i, (num, title, col, desc) in enumerate(steps):
        y = 140 + i*92
        d.ellipse([60, y, 102, y+42], fill=col)
        d.text((76, y+11), num, fill=(0,0,0))
        d.text((120, y+6), title, fill=TEXT)
        d.text((120, y+28), desc, fill=MUTED)
        if i < len(steps)-1:
            d.line([81, y+44, 81, y+90], fill=(40,45,55), width=2)
    d.rectangle([60, 614, 560, 652], fill=ACCENT)
    d.text((130, 626), "github.com/PapaKoftes/VibeSort", fill=TEXT)
    return img


frames = [frame_home(), frame_vibes(), frame_badges(), frame_atlas(), frame_deploy()]
names  = ["home_dashboard", "vibes_cards", "signal_badges", "mood_atlas_grid", "deploy_flow"]

for frame, name in zip(frames, names):
    frame.save(OUT / f"{name}.png")
    print(f"  {name}.png")

frames[0].save(
    "docs/vibesort_demo.gif",
    save_all=True,
    append_images=frames[1:],
    duration=[3200, 3000, 3500, 3000, 3200],
    loop=0,
)
print(f"vibesort_demo.gif saved ({len(frames)} frames)")
