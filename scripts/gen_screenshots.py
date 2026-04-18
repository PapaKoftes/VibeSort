"""Generate demo screenshots and GIF from `outputs/.last_scan_snapshot.json`.

Run from repo root after a full scan:

    python scripts/gen_screenshots.py

Requires: Pillow, matplotlib, numpy (see requirements.txt). Writes:
  docs/vibesort_demo.gif
  docs/screenshots/*.png (README + docs/GUIDE.md)

If the snapshot is missing, exits with a clear message (do not commit empty assets).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import shutil

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SNAP_PATH = ROOT / "outputs" / ".last_scan_snapshot.json"
PACKS_PATH = ROOT / "data" / "packs.json"
OUT = ROOT / "docs" / "screenshots"
GIF_PATH = ROOT / "docs" / "vibesort_demo.gif"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def mood_track_count(info: dict) -> int:
    if info.get("count") is not None:
        return int(info["count"])
    return len(info.get("ranked") or [])


def unique_artist_ids(all_tracks: list[dict]) -> int:
    s: set[str] = set()
    for t in all_tracks:
        for a in t.get("artists") or []:
            aid = a.get("id")
            if aid:
                s.add(aid)
    return len(s)


def main() -> None:
    if not SNAP_PATH.exists():
        print(f"Missing {SNAP_PATH} — run a full Scan in the app first.", file=sys.stderr)
        sys.exit(1)

    snap = _load_json(SNAP_PATH)
    packs = _load_json(PACKS_PATH) if PACKS_PATH.exists() else {}
    total_pack_moods = len(packs.get("moods") or {})

    all_tracks: list[dict] = snap.get("all_tracks") or []
    mood_results: dict[str, dict] = snap.get("mood_results") or {}
    genre_map = snap.get("genre_map") or {}

    n_tracks = len(all_tracks)
    n_moods_scored = len(mood_results)
    n_genres_ui = len(genre_map)
    n_artists = unique_artist_ids(all_tracks)

    sorted_moods = sorted(
        mood_results.items(),
        key=lambda x: -mood_track_count(x[1]),
    )
    top_labels = [m for m, _ in sorted_moods[:30]]
    top_counts = [mood_track_count(info) for _, info in sorted_moods[:30]]

    OUT.mkdir(parents=True, exist_ok=True)

    # ── 1. Mood Atlas bar chart (matplotlib) ───────────────────────────────────
    max_c = max(top_counts) if top_counts else 1
    colors = [
        "#6366f1" if c >= 30 else "#818cf8" if c >= 25 else "#a78bfa" if c >= 20 else "#c4b5fd"
        for c in top_counts
    ]

    fig, ax = plt.subplots(figsize=(16, 6))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")
    x = np.arange(len(top_labels))
    bars = ax.bar(x, top_counts, color=colors, width=0.7, edgecolor="#0e1117", linewidth=0.5)
    for bar, cnt in zip(bars, top_counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_c * 0.01,
            str(cnt),
            ha="center",
            va="bottom",
            color="white",
            fontsize=8,
            fontweight="bold",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(top_labels, rotation=45, ha="right", color="white", fontsize=9.5)
    ax.tick_params(axis="y", colors="#9ca3af", labelsize=9)
    ax.set_ylabel("tracks in playlist", color="#9ca3af", fontsize=10)
    ax.spines[:].set_visible(False)
    ax.set_ylim(0, max_c * 1.15)
    legend = [
        mpatches.Patch(color="#6366f1", label="30+ tracks"),
        mpatches.Patch(color="#818cf8", label="25–29 tracks"),
        mpatches.Patch(color="#a78bfa", label="20–24 tracks"),
        mpatches.Patch(color="#c4b5fd", label="<20 tracks"),
    ]
    ax.legend(
        handles=legend,
        facecolor="#1a1a2e",
        edgecolor="#333",
        labelcolor="white",
        fontsize=9,
        loc="upper right",
    )
    fig.suptitle(
        "Mood Atlas — top 30 vibes by track count",
        color="white",
        fontsize=14,
        fontweight="bold",
        y=1.0,
    )
    plt.tight_layout()
    plt.savefig(OUT / "mood_atlas.png", dpi=150, bbox_inches="tight", facecolor="#0e1117")
    plt.close()
    print("mood_atlas.png")

    # ── 2. PIL demo frames ─────────────────────────────────────────────────────
    W, H = 1200, 700
    BG = (14, 17, 23)
    ACCENT = (99, 102, 241)
    GREEN = (34, 197, 94)
    TEXT = (255, 255, 255)
    MUTED = (156, 163, 175)
    CARD = (22, 27, 34)
    PURPLE = (167, 139, 250)
    DARK_CARD = (21, 27, 38)
    ORANGE = (245, 158, 11)

    moods_label = str(n_moods_scored)
    packs_label = str(total_pack_moods or n_moods_scored)

    def header(img: Image.Image, d: ImageDraw.ImageDraw, title: str, subtitle: str) -> None:
        d.rectangle([0, 0, W, 52], fill=(18, 22, 30))
        d.text((20, 16), "Vibesort", fill=TEXT)
        d.text((W - 130, 16), "localhost:8501", fill=MUTED)
        d.text((60, 68), title, fill=TEXT)
        d.text((60, 92), subtitle, fill=MUTED)
        d.line([60, 118, W - 60, 118], fill=(40, 45, 55), width=1)

    # Stats row — mirror Home summary tiles (numbers from snapshot)
    stat_row = [
        (_fmt_int(n_tracks), "Tracks"),
        (moods_label, "Moods"),
        (_fmt_int(n_genres_ui), "Genre groups"),
        (_fmt_int(n_artists), "Artists"),
    ]

    top_for_blurb = [m for m, _ in sorted_moods[:3]]
    blurb = (
        f"Strong lean toward {top_for_blurb[0]}, {top_for_blurb[1]}, and {top_for_blurb[2]} — "
        f"from your latest scan."
        if len(top_for_blurb) >= 3
        else "After scan — browse Vibes to explore mood playlists."
    )

    # Illustrative fingerprint shares (UI families); totals stay readable vs. library size
    bars_data = [
        ("Power / Energy", 0.26, (239, 68, 68)),
        ("Party / Dance", 0.22, ORANGE),
        ("Chill / Focus", 0.18, (34, 197, 94)),
        ("Dark / Introspective", 0.17, ACCENT),
        ("Story / Roots", 0.17, PURPLE),
    ]

    def frame_home() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(img, d, "Your Library Dashboard", "After scan — here's what Vibesort found")
        for i, (val, lbl) in enumerate(stat_row):
            x = 60 + i * 240
            d.rectangle([x, 138, x + 200, 220], fill=CARD)
            d.text((x + 20, 148), val, fill=TEXT)
            d.text((x + 20, 175), lbl, fill=MUTED)
        start_track = sorted_moods[0][0] if sorted_moods else "—"
        start_meta = (
            f"{mood_track_count(sorted_moods[0][1])} tracks · top match"
            if sorted_moods
            else ""
        )
        d.rectangle([60, 238, 920, 282], fill=(21, 47, 30))
        d.text(
            (80, 252),
            f"Start here:  {start_track}  —  {start_meta}",
            fill=GREEN,
        )
        d.rectangle([930, 238, 1100, 282], fill=ACCENT)
        d.text((970, 252), "Open it", fill=TEXT)
        d.text((60, 308), "Your library's emotional fingerprint", fill=TEXT)
        d.rectangle([60, 334, 1100, 370], fill=DARK_CARD)
        d.text((80, 348), blurb[:180] + ("…" if len(blurb) > 180 else ""), fill=MUTED)
        base_tracks = max(n_tracks, 1)
        for i, (lbl, pct, col) in enumerate(bars_data):
            y = 388 + i * 44
            bw = int(660 * pct)
            d.rectangle([60, y, 60 + bw, y + 30], fill=col)
            d.rectangle([60 + bw, y, 720, y + 30], fill=(40, 45, 55))
            approx = int(pct * base_tracks)
            d.text((730, y + 8), f"{lbl}  {round(pct * 100)}%  (~{approx} tracks)", fill=TEXT)
        return img

    # Vibes grid: take up to 6 moods from live ranking
    demo_moods: list[tuple[str, str, str, float]] = []
    for name, info in sorted_moods[:6]:
        cnt = mood_track_count(info)
        coh = float(info.get("cohesion") or 0.7)
        fit = "Great fit" if coh >= 0.72 else "Good fit" if coh >= 0.55 else "Mixed"
        demo_moods.append((name, f"{cnt} tracks", fit, min(0.95, max(0.35, coh))))

    while len(demo_moods) < 6:
        demo_moods.append(("Example Mood", "20 tracks", "Good fit", 0.65))

    def frame_vibes() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(
            img,
            d,
            "Your Vibes",
            f"{moods_label} mood playlists sorted by fit quality",
        )
        d.text(
            (60, 128),
            f"{packs_label} mood packs · {moods_label} active in your library after gates",
            fill=MUTED,
        )
        for i, (name, count, fit, coh) in enumerate(demo_moods):
            col = i % 3
            row = i // 3
            x = 60 + col * 375
            y = 155 + row * 215
            d.rectangle([x, y, x + 350, y + 200], fill=CARD)
            d.text((x + 14, y + 14), name, fill=TEXT)
            d.text((x + 14, y + 36), f"{count}  ·  match quality: {fit}", fill=MUTED)
            bw = int(320 * coh)
            d.rectangle([x + 14, y + 62, x + 14 + bw, y + 74], fill=ACCENT)
            d.rectangle([x + 14 + bw, y + 62, x + 334, y + 74], fill=(40, 45, 55))
            d.rectangle([x + 14, y + 162, x + 334, y + 188], fill=ACCENT)
            d.text((x + 110, y + 169), "Build playlist", fill=TEXT)
        return img

    def frame_badges() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(img, d, "Track signal badges", "Why each track landed in this mood")
        first = sorted_moods[0][0] if sorted_moods else "Hollow"
        first_n = mood_track_count(sorted_moods[0][1]) if sorted_moods else 0
        d.rectangle([60, 130, 1100, 660], fill=CARD)
        d.text((78, 142), f"{first}  —  sample tracklist ({first_n} tracks)", fill=TEXT)
        d.line([78, 168, 1082, 168], fill=(40, 45, 55), width=1)
        d.text(
            (78, 178),
            "Badges combine anchors, listening history, similarity, crowd tags, and lyrics.",
            fill=MUTED,
        )
        d.text(
            (78, 198),
            "Keys: [Anchor] [Personal] [Similar] [Last.fm] [Lyrics]",
            fill=(107, 114, 128),
        )
        d.line([78, 218, 1082, 218], fill=(40, 45, 55), width=1)
        tracks = [
            ("How", "The Neighbourhood", "[Anchor]  [Personal]  [Last.fm]", "Alternative Rock"),
            ("My Iron Lung", "Radiohead", "[Anchor]  [Similar]", "Alternative"),
            ("Hollow", "Artist name", "[Last.fm]  [Lyrics]", "Alternative"),
            ("Skinny Love", "Bon Iver", "[Similar]  [Lyrics]", "Indie Folk"),
            ("Devil Town", "Cavetown", "[Personal]  [Lyrics]", "Bedroom Pop"),
            ("Many Men", "50 Cent", "[Anchor]  [Last.fm]", "East Coast Rap"),
            ("Without Me", "Eminem", "[Anchor]  [Last.fm]", "Hip Hop"),
        ]
        for i, (name, artist, badges, genre) in enumerate(tracks):
            y = 234 + i * 56
            d.text((95, y), name, fill=TEXT)
            d.text((95, y + 20), artist, fill=MUTED)
            d.text((380, y + 6), badges, fill=PURPLE)
            d.text((960, y + 6), genre, fill=(75, 85, 99))
        return img

    strong = [(m, mood_track_count(info)) for m, info in sorted_moods if mood_track_count(info) >= 30][:5]
    present = [
        (m, mood_track_count(info))
        for m, info in sorted_moods
        if 20 <= mood_track_count(info) < 30
    ][:5]
    thin = [(m, mood_track_count(info)) for m, info in sorted_moods if mood_track_count(info) < 20][:5]

    def fmt_lines(pairs: list[tuple[str, int]]) -> list[str]:
        return [f"{m} ({n})" for m, n in pairs] or ["—"]

    def frame_atlas_grid() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(
            img,
            d,
            "Mood Atlas",
            f"{packs_label} packs · snapshot overview (illustrative tiers)",
        )
        missing_n = max(0, (total_pack_moods or n_moods_scored) - n_moods_scored)
        d.text(
            (60, 128),
            f"{packs_label} total moods  ·  {n_moods_scored} scored this scan"
            + (f"  ·  {missing_n} not surfaced" if missing_n else ""),
            fill=MUTED,
        )
        sections = [
            ("STRONG (30+ tracks)", (99, 102, 241), fmt_lines(strong)),
            ("PRESENT (20–29 tracks)", (129, 140, 248), fmt_lines(present)),
            ("THIN (<20 tracks)", (196, 181, 253), fmt_lines(thin)),
            ("DISCOVERY", (75, 85, 99), ["Use Vibes filters and anchors to widen thin moods."]),
        ]
        y = 150
        for label, col, items in sections:
            d.rectangle([60, y, 86, y + 22], fill=col)
            d.text((96, y + 4), label, fill=TEXT)
            y += 28
            for item in items:
                d.text((100, y), item, fill=MUTED)
                y += 22
            y += 12
        d.rectangle([60, 560, 1100, 640], fill=DARK_CARD)
        d.text((80, 572), "Tip: rescan after adding liked songs or new anchors in data/mood_anchors.json", fill=PURPLE)
        return img

    def frame_deploy() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(img, d, "Deploy to Spotify", "Queue playlists, rename them, push in one click")
        steps = [
            ("1", "Connect to Spotify", GREEN, "OAuth in your browser"),
            ("2", "Scan your library", GREEN, "First run is slower; results are cached."),
            ("3", f"Browse {moods_label} mood playlists", GREEN, "Sorted by fit quality; badges explain tracks."),
            ("4", "Build + queue on Staging", ORANGE, "Rename, preview, toggle recommendations."),
            ("5", "Deploy to Spotify", ACCENT, "Create all queued playlists in one shot."),
        ]
        for i, (num, title, col, desc) in enumerate(steps):
            y = 140 + i * 92
            d.ellipse([60, y, 102, y + 42], fill=col)
            d.text((76, y + 11), num, fill=(0, 0, 0))
            d.text((120, y + 6), title, fill=TEXT)
            d.text((120, y + 28), desc, fill=MUTED)
            if i < len(steps) - 1:
                d.line([81, y + 44, 81, y + 90], fill=(40, 45, 55), width=2)
        d.rectangle([60, 614, 560, 652], fill=ACCENT)
        d.text((130, 626), "github.com/PapaKoftes/VibeSort", fill=TEXT)
        return img

    def frame_connect() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(img, d, "Connect", "Spotify + optional enrichments")
        d.rectangle([120, 200, 1080, 420], fill=CARD)
        d.text((160, 230), "Connect to Spotify (PKCE)", fill=TEXT)
        d.text((160, 260), "Uses the shared client ID or your own app from Settings.", fill=MUTED)
        d.rectangle([160, 310, 520, 370], fill=ACCENT)
        d.text((215, 328), "Connect to Spotify", fill=TEXT)
        d.text((160, 390), "Optional: Last.fm / ListenBrainz tokens for richer tags (Settings).", fill=MUTED)
        return img

    def frame_scan() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(img, d, "Scan library", "Full scan · custom refresh · optional local AcoustID")
        lines = [
            "• Full library — liked songs, tops, followed artists, saved playlists",
            "• Custom scan — clear selected caches (mining, lyrics, …)",
            "• Local audio — optional Chromaprint / AcoustID when configured",
            f"• Last snapshot: {_fmt_int(n_tracks)} tracks ingested",
        ]
        y = 200
        for line in lines:
            d.text((80, y), line, fill=TEXT)
            y += 44
        d.rectangle([80, 520, 420, 580], fill=GREEN)
        d.text((130, 542), "Scan library", fill=(10, 20, 10))
        return img

    def frame_staging() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(img, d, "Staging", "Rename · preview · deploy batches to Spotify")
        d.text((60, 200), "Queued playlists appear here before creation in Spotify.", fill=MUTED)
        d.rectangle([60, 250, 1100, 360], fill=CARD)
        d.text((80, 270), "Bedroom Pop Diary → rename → preview tracks → toggle recs", fill=TEXT)
        d.rectangle([80, 520, 420, 580], fill=ACCENT)
        d.text((125, 542), "Deploy all to Spotify", fill=TEXT)
        return img

    def frame_stats() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(img, d, "Stats", "Taste report — library shape, obscurity, genres, eras")
        d.text((60, 200), f"Tracks {_fmt_int(n_tracks)}  ·  Artists {_fmt_int(n_artists)}  ·  Mood playlists {moods_label}", fill=TEXT)
        d.text((60, 250), "Includes genre/era breakdowns, vibe summaries, and enrichment coverage.", fill=MUTED)
        return img

    def frame_settings() -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header(img, d, "Settings", "Keys, scoring weights, enrichment toggles, cache control")
        items = [
            "Connections — Spotify app override, Last.fm, ListenBrainz",
            "Playlist generation — strictness, MVP fallback, minimum totals",
            "Enrichment — AudioDB, Discogs, lyrics, MusicBrainz, …",
            "Caching — clear per-source or reset snapshot",
        ]
        y = 200
        for it in items:
            d.text((80, y), f"• {it}", fill=TEXT)
            y += 48
        return img

    home_img = frame_home()
    fingerprint = home_img.crop((56, 292, 1144, 668))
    fingerprint.save(OUT / "fingerprint.png")
    print("fingerprint.png (crop from home)")

    pil_exports: list[tuple[str, object]] = [
        ("home_dashboard", home_img),
        ("vibes_cards", frame_vibes()),
        ("signal_badges", frame_badges()),
        ("mood_atlas_grid", frame_atlas_grid()),
        ("deploy_flow", frame_deploy()),
        ("connect", frame_connect()),
        ("scan", frame_scan()),
        ("staging", frame_staging()),
        ("stats", frame_stats()),
        ("settings", frame_settings()),
    ]

    for name, img in pil_exports:
        img.save(OUT / f"{name}.png")
        print(f"  {name}.png")

    # GUIDE uses vibes.png — keep in sync with vibes_cards
    shutil.copy2(OUT / "vibes_cards.png", OUT / "vibes.png")
    print("  vibes.png (copy of vibes_cards)")

    frames = [home_img, frame_vibes(), frame_badges(), frame_atlas_grid(), frame_deploy()]
    frames[0].save(
        GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=[3200, 3000, 3500, 3000, 3200],
        loop=0,
    )
    print(f"{GIF_PATH.name} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
