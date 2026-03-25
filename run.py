"""
run.py — Vibesort entry point.

Flow:
  1. Connect to Spotify
  2. Scan library + run playlist mining
  3. Score your library against every mood in packs.json
  4. Show discovered vibes ranked by cohesion
  5. Pick a vibe → preview → optionally expand with recs → create

Usage:
  python run.py
"""

import sys
import os

try:
    import spotipy
    from dotenv import load_dotenv
except ImportError:
    print("\n[ERROR] Dependencies not installed. Run: pip install -r requirements.txt\n")
    sys.exit(1)

# Ensure we can import from current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core import ingest, enrich, genre as genre_mod, playlist_mining, profile as profile_mod
from core import scorer, cohesion as cohesion_mod, recommend, builder
from core import history_parser
from core.mood_graph import all_moods, fuzzy_match, related_moods, cosine_similarity


SCOPE = (
    "user-library-read user-top-read user-follow-read "
    "playlist-read-private playlist-read-collaborative "
    "playlist-modify-private playlist-modify-public"
)


# ── UI ─────────────────────────────────────────────────────────────────────────

WIDTH = 60

def banner():
    print()
    print("  " + "─" * WIDTH)
    print("  {:^{w}}".format("V I B E S O R T", w=WIDTH))
    print("  {:^{w}}".format("your library, sorted by feeling", w=WIDTH))
    print("  " + "─" * WIDTH)
    print()


def section(title: str):
    print()
    print("  " + "─" * WIDTH)
    print(f"  {title}")
    print("  " + "─" * WIDTH)


def ask(prompt: str, default: str = "") -> str:
    suffix = f"  (default: {default})" if default else ""
    try:
        val = input(f"\n  {prompt}{suffix}\n  > ").strip()
        return val or default
    except (KeyboardInterrupt, EOFError):
        print("\n  Bye.")
        sys.exit(0)


def confirm(prompt: str, default: bool = False) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    val = ask(f"{prompt} {hint}")
    if not val:
        return default
    return val.lower() in ("y", "yes")


def progress(msg: str, done: bool = False):
    if done:
        print(f"\r  {msg:<{WIDTH}}")
    else:
        print(f"  {msg}", end="", flush=True)


# ── Spotify auth ──────────────────────────────────────────────────────────────

def connect() -> tuple[spotipy.Spotify, dict]:
    if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
        print("\n  [ERROR] Credentials not set. Copy .env.example to .env and fill in your keys.")
        print("  Get them at: https://developer.spotify.com/dashboard\n")
        sys.exit(1)

    sp = spotipy.Spotify(auth_manager=spotipy.oauth2.SpotifyOAuth(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=config.SPOTIFY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=".vibesort_cache",
        open_browser=True,
    ))
    me = sp.current_user()
    return sp, me


# ── Session state (loaded once, reused across menu) ───────────────────────────

_session: dict = {}


def load_session(sp: spotipy.Spotify, user_id: str) -> dict:
    if _session:
        return _session

    section("SCANNING YOUR LIBRARY")

    # Step 1: Ingest
    all_tracks, top_tracks_list, top_artists_list = ingest.collect(sp, config)

    # Step 2: Enrich
    artist_genres_map, audio_features_map = enrich.gather(sp, all_tracks)

    # Step 3: Playlist mining (the core signal)
    moods = all_moods()
    user_uris = {t["uri"] for t in all_tracks if t.get("uri")}
    print("  Playlist mining       (first run ~30s, then cached)")
    mining = playlist_mining.mine(
        sp, user_uris, moods,
        playlists_per_seed=config.PLAYLISTS_PER_SEED,
        force_refresh=config.MINING_FORCE_REFRESH,
    )
    track_tags = mining.get("track_tags", {})

    # Step 4: Build track profiles
    print("  Building track profiles...", end="", flush=True)
    profiles = profile_mod.build_all(all_tracks, artist_genres_map, audio_features_map, track_tags)
    print(f"\r  Track profiles        {len(profiles)} built")

    # Step 5: User taste vectors
    user_mean = profile_mod.user_audio_mean(profiles)

    # Step 6: Genre/era/artist breakdowns
    genre_map  = genre_mod.library_genre_breakdown(all_tracks, artist_genres_map)
    era_map    = genre_mod.era_breakdown(all_tracks)
    artist_map = genre_mod.artist_breakdown(all_tracks, config.MIN_SONGS_PER_ARTIST)

    # Step 7: Score every mood against the library
    print("  Scoring moods against library...", end="", flush=True)
    mood_results: dict[str, dict] = {}
    for mood_name in moods:
        ranked = scorer.rank_tracks(
            profiles, mood_name, user_mean,
            min_score=0.22,
            weights=(config.W_AUDIO, config.W_TAGS, config.W_GENRE),
        )
        if not ranked:
            continue
        top_uris = [u for u, _ in ranked[:config.MAX_TRACKS_PER_PLAYLIST * 2]]
        filtered, c_score = cohesion_mod.top_n_by_score(
            ranked, profiles,
            n=config.MAX_TRACKS_PER_PLAYLIST,
            cohesion_threshold=config.COHESION_THRESHOLD,
            min_tracks=5,
        )
        if len(filtered) >= 5:
            mood_results[mood_name] = {
                "uris":     filtered,
                "cohesion": c_score,
                "count":    len(filtered),
            }
    print(f"\r  Moods discovered      {len(mood_results)} vibes found in your library")

    # Step 8: Full history if available
    history_entries = history_parser.load("data")
    history_stats = history_parser.stats(history_entries) if history_entries else {}
    history_uris  = history_parser.sorted_uris(history_entries) if history_entries else []

    _session.update({
        "sp":               sp,
        "user_id":          user_id,
        "all_tracks":       all_tracks,
        "top_tracks":       top_tracks_list,
        "top_artists":      top_artists_list,
        "profiles":         profiles,
        "user_mean":        user_mean,
        "artist_genres":    artist_genres_map,
        "audio_features":   audio_features_map,
        "track_tags":       track_tags,
        "genre_map":        genre_map,
        "era_map":          era_map,
        "artist_map":       artist_map,
        "mood_results":     mood_results,
        "history_stats":    history_stats,
        "history_uris":     history_uris,
        "existing_uris":    user_uris,
    })
    return _session


# ── Vibe display ──────────────────────────────────────────────────────────────

def show_vibes_overview(mood_results: dict, moods_meta: dict, top_n: int = 10):
    """Print the top N vibes sorted by cohesion."""
    sorted_moods = sorted(mood_results.items(), key=lambda x: -x[1]["cohesion"])
    print(f"\n  {'VIBE':<25} {'TRACKS':>7}  {'COHESION':>10}  DESCRIPTION")
    print("  " + "─" * WIDTH)
    for i, (name, info) in enumerate(sorted_moods[:top_n], 1):
        desc = moods_meta.get(name, {}).get("description", "")[:28]
        c_label = cohesion_mod.cohesion_label(info["cohesion"])
        print(f"  {i:>2}. {name:<22} {info['count']:>4} tracks  {info['cohesion']*100:>5.0f}%  {desc}")
    if len(sorted_moods) > top_n:
        print(f"\n  ... and {len(sorted_moods) - top_n} more vibes. Type 'more' to see all.")
    return sorted_moods


def show_vibe_preview(mood_name: str, info: dict, profiles: dict, top_n: int = 5):
    """Print a preview card for a vibe."""
    from core.mood_graph import get_mood
    pack = get_mood(mood_name) or {}
    desc = pack.get("description", "")
    c_label = cohesion_mod.cohesion_label(info["cohesion"])

    print(f"\n  ┌{'─'*(WIDTH-2)}┐")
    print(f"  │  {mood_name.upper():<{WIDTH-5}}│")
    print(f"  │  {desc:<{WIDTH-5}}│")
    print(f"  │  {info['count']} tracks · {info['cohesion']*100:.0f}% cohesive ({c_label}){' '*(WIDTH - 5 - len(str(info['count'])) - len(c_label) - 23)}│")
    print(f"  └{'─'*(WIDTH-2)}┘")

    print(f"\n  Top tracks in this vibe:")
    for uri in info["uris"][:top_n]:
        p = profiles.get(uri)
        if p:
            artists = ", ".join(p["artists"][:2])
            print(f"    • {p['name'][:35]:<35}  {artists[:25]}")

    related = related_moods(mood_name, top_n=2)
    if related:
        print(f"\n  You might also like: {', '.join(related)}")


# ── Actions ───────────────────────────────────────────────────────────────────

def action_create_vibe(data: dict, mood_name: str, info: dict):
    """Full flow: preview → confirm → optionally add recs → create in Spotify."""
    show_vibe_preview(mood_name, info, data["profiles"])

    if not confirm("\n  Create this playlist in Spotify?"):
        print("  Skipped.")
        return

    rec_uris: list[str] = []
    if confirm(f"  Add similar songs (recommendations)?", default=True):
        print("  Fetching recommendations...", end="", flush=True)
        rec_uris = recommend.filtered_recommendations(
            sp=data["sp"],
            seed_uris=info["uris"],
            profiles=data["profiles"],
            existing_uris=data["existing_uris"],
            mood_name=mood_name,
            n=config.RECS_PER_PLAYLIST,
        )
        print(f"\r  Recommendations: {len(rec_uris)} similar songs found")

    print("  Creating playlist...", end="", flush=True)
    url = builder.build_mood_playlist(
        sp=data["sp"],
        user_id=data["user_id"],
        mood_name=mood_name,
        track_uris=info["uris"],
        cohesion=info["cohesion"],
        rec_uris=rec_uris if rec_uris else None,
        prefix=config.PLAYLIST_PREFIX,
    )
    print(f"\r  Created: {url}")


def action_pick_vibe(data: dict):
    """Show all vibes, let user pick one or more to create."""
    section("PICK A VIBE")
    moods_meta = all_moods()
    sorted_moods = show_vibes_overview(data["mood_results"], moods_meta)

    while True:
        raw = ask("Enter vibe number, name, or keyword (or 'done' to go back)", default="done")
        if raw.lower() in ("done", "back", "q", ""):
            break
        if raw.lower() == "more":
            show_vibes_overview(data["mood_results"], moods_meta, top_n=99)
            continue

        # Try number
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(sorted_moods):
                mood_name, info = sorted_moods[idx]
                action_create_vibe(data, mood_name, info)
                continue

        # Try exact name
        if raw in data["mood_results"]:
            action_create_vibe(data, raw, data["mood_results"][raw])
            continue

        # Fuzzy match
        matches = fuzzy_match(raw, top_n=3)
        valid = [(n, s) for n, s in matches if n in data["mood_results"] and s > 0]
        if valid:
            print(f"\n  Closest matches to '{raw}':")
            for i, (n, s) in enumerate(valid, 1):
                info = data["mood_results"][n]
                print(f"    [{i}] {n:<25} ({info['count']} tracks, {info['cohesion']*100:.0f}% cohesive)")
            choice = ask("Pick a number or press Enter to skip", default="")
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(valid):
                    mood_name = valid[idx][0]
                    action_create_vibe(data, mood_name, data["mood_results"][mood_name])
        else:
            print(f"  No matching vibe found for '{raw}'.")


def action_create_all_vibes(data: dict):
    """Create all discovered vibes at once."""
    section("CREATE ALL VIBES")
    moods_meta = all_moods()
    sorted_moods = sorted(data["mood_results"].items(), key=lambda x: -x[1]["cohesion"])

    print(f"\n  This will create {len(sorted_moods)} playlists in your Spotify.")
    want_recs = confirm("  Add recommendations to each?", default=True)

    if not confirm("\n  Ready to go?"):
        return

    for mood_name, info in sorted_moods:
        rec_uris: list[str] = []
        if want_recs:
            rec_uris = recommend.filtered_recommendations(
                data["sp"], info["uris"], data["profiles"],
                data["existing_uris"], mood_name, n=config.RECS_PER_PLAYLIST,
            )
        url = builder.build_mood_playlist(
            data["sp"], data["user_id"], mood_name,
            info["uris"], info["cohesion"],
            rec_uris or None, config.PLAYLIST_PREFIX,
        )
        print(f"  {mood_name:<25}  {url}")


def action_genre_playlists(data: dict):
    """Create playlists grouped by macro genre."""
    section("GENRE PLAYLISTS")
    valid = {g: uris for g, uris in data["genre_map"].items() if len(uris) >= config.MIN_SONGS_PER_GENRE}
    if not valid:
        print("  Not enough tracks per genre.")
        return

    print(f"\n  {'GENRE':<30} {'TRACKS':>7}")
    print("  " + "─" * 40)
    for g, uris in sorted(valid.items(), key=lambda x: -len(x[1])):
        print(f"  {g:<30} {len(uris):>4} tracks")

    if not confirm(f"\n  Create {len(valid)} genre playlists?"):
        return

    want_recs = confirm("  Add recommendations to each?", default=True)
    for g, uris in sorted(valid.items(), key=lambda x: -len(x[1])):
        rec_uris = []
        if want_recs:
            rec_uris = recommend.filtered_recommendations(
                data["sp"], uris, data["profiles"], data["existing_uris"],
                mood_name=None, n=config.RECS_PER_PLAYLIST,
            )
        url = builder.build_genre_playlist(
            data["sp"], data["user_id"], g, uris,
            rec_uris or None, config.PLAYLIST_PREFIX,
        )
        print(f"  {g:<30}  {url}")


def action_era_playlists(data: dict):
    """Create playlists by decade."""
    section("ERA PLAYLISTS")
    valid = {e: uris for e, uris in data["era_map"].items() if len(uris) >= config.MIN_SONGS_PER_ERA}
    if not valid:
        print("  Not enough tracks per era.")
        return

    print(f"\n  {'ERA':<15} {'TRACKS':>7}")
    for e, uris in sorted(valid.items(), key=lambda x: x[0]):
        print(f"  {e:<15} {len(uris):>4} tracks")

    if not confirm(f"\n  Create {len(valid)} era playlists?"):
        return

    for e, uris in sorted(valid.items()):
        url = builder.build_generic_playlist(
            data["sp"], data["user_id"], e, uris,
            description=f"{e}. {len(uris)} tracks. Made by Vibesort.",
            prefix=config.PLAYLIST_PREFIX,
        )
        print(f"  {e:<15}  {url}")


def action_artist_playlists(data: dict):
    """Create spotlight playlists for your most-present artists."""
    section("ARTIST SPOTLIGHTS")
    valid = data["artist_map"]
    if not valid:
        print("  Not enough tracks per artist (need 8+).")
        return

    sorted_artists = sorted(valid.items(), key=lambda x: -len(x[1]))
    print(f"\n  Top artists in your library:")
    for name, uris in sorted_artists[:15]:
        print(f"  {name:<35} {len(uris):>4} tracks")

    if not confirm(f"\n  Create {len(valid)} artist spotlight playlists?"):
        return

    for name, uris in sorted_artists:
        url = builder.build_generic_playlist(
            data["sp"], data["user_id"], name, uris,
            description=f"Everything in your library by {name}.",
            prefix=config.PLAYLIST_PREFIX,
        )
        print(f"  {name:<35}  {url}")


def action_heavy_rotation(data: dict):
    """Create a Heavy Rotation playlist from actual top tracks."""
    section("HEAVY ROTATION")
    uris = list(dict.fromkeys(t["uri"] for t in data["top_tracks"] if t.get("uri")))
    if not uris:
        print("  No top track data available.")
        return

    print(f"\n  {len(uris)} tracks from your short/medium/long-term listening.")
    if data["history_uris"]:
        extra = [u for u in data["history_uris"][:50] if u not in set(uris)]
        uris = uris + extra[:20]
        print(f"  + {min(20, len(data['history_uris'][:50]))} from your full history export.")

    want_recs = confirm("  Add recommendations?", default=True)
    rec_uris = []
    if want_recs:
        rec_uris = recommend.filtered_recommendations(
            data["sp"], uris, data["profiles"], data["existing_uris"],
            mood_name=None, n=config.RECS_PER_PLAYLIST,
        )

    url = builder.build_generic_playlist(
        data["sp"], data["user_id"], "Heavy Rotation", uris,
        rec_uris=rec_uris or None,
        description=f"Your most-played tracks across all time. {len(uris)} songs.",
        prefix=config.PLAYLIST_PREFIX,
    )
    print(f"\n  Created: {url}")


def action_stats(data: dict):
    """Print a quick taste report."""
    section("YOUR TASTE REPORT")

    tracks = data["all_tracks"]
    pops = [t.get("popularity", 50) for t in tracks if t.get("popularity") is not None]
    avg_pop = sum(pops) / len(pops) if pops else 50
    obscurity = round(100 - avg_pop, 1)

    obscurity_label = (
        "deep underground" if obscurity >= 65 else
        "leaning underground" if obscurity >= 45 else
        "balanced taste" if obscurity >= 30 else
        "mostly mainstream"
    )

    # Top genre
    top_genre = max(data["genre_map"].items(), key=lambda x: len(x[1]), default=("?", []))
    # Top era
    top_era   = max(data["era_map"].items(), key=lambda x: len(x[1]), default=("?", []))

    # Audio averages
    features_list = list(data["audio_features"].values())
    def avg_feat(key): return round(sum(f.get(key, 0) for f in features_list) / len(features_list), 2) if features_list else 0

    energy       = avg_feat("energy")
    valence      = avg_feat("valence")
    danceability = avg_feat("danceability")
    acousticness = avg_feat("acousticness")
    instrumental = avg_feat("instrumentalness")
    tempos       = [f.get("tempo", 120) for f in features_list]
    avg_tempo    = round(sum(tempos) / len(tempos)) if tempos else 0

    def bar(v, w=16): return "[" + "#" * int(v * w) + "-" * (w - int(v * w)) + "]"

    print(f"\n  Library: {len(tracks)} unique tracks  |  {len(data['genre_map'])} genres  |  {len(data['era_map'])} eras")
    print(f"\n  Obscurity score:  {obscurity}/100  ({obscurity_label})")
    print(f"\n  Top genre:  {top_genre[0]}  ({len(top_genre[1])} tracks)")
    print(f"  Top era:    {top_era[0]}  ({len(top_era[1])} tracks)")

    print(f"\n  YOUR AUDIO FINGERPRINT")
    print(f"  {'Energy':<18} {energy:.2f}  {bar(energy)}")
    print(f"  {'Positivity':<18} {valence:.2f}  {bar(valence)}")
    print(f"  {'Danceability':<18} {danceability:.2f}  {bar(danceability)}")
    print(f"  {'Acousticness':<18} {acousticness:.2f}  {bar(acousticness)}")
    print(f"  {'Instrumental':<18} {instrumental:.2f}  {bar(instrumental)}")
    print(f"  {'Avg Tempo':<18} {avg_tempo} BPM")

    print(f"\n  TOP VIBES IN YOUR LIBRARY")
    sorted_moods = sorted(data["mood_results"].items(), key=lambda x: -x[1]["cohesion"])
    for name, info in sorted_moods[:5]:
        print(f"  {name:<25} {info['count']:>4} tracks  {info['cohesion']*100:.0f}% cohesive")

    if data["history_stats"]:
        print(f"\n  FROM YOUR DATA EXPORT")
        hs = data["history_stats"]
        print(f"  Total streams:  {hs.get('total_streams', '?')}")
        print(f"  Hours listened: {hs.get('total_hours', '?')}")
        print(f"  Since:          {hs.get('earliest', '?')}")

    # Save to file
    os.makedirs("outputs", exist_ok=True)
    report_lines = [
        "VIBESORT — TASTE REPORT", "=" * 50,
        f"Library: {len(tracks)} tracks",
        f"Obscurity: {obscurity}/100 ({obscurity_label})",
        f"Top genre: {top_genre[0]}",
        f"Top era: {top_era[0]}",
        f"Energy avg: {energy}",
        f"Valence avg: {valence}",
        f"Danceability: {danceability}",
        f"Tempo avg: {avg_tempo} BPM",
    ]
    with open("outputs/taste_report.txt", "w") as f:
        f.write("\n".join(report_lines))
    print("\n  Saved to outputs/taste_report.txt")


# ── Main menu ─────────────────────────────────────────────────────────────────

MENU = [
    ("1", "Pick a vibe and generate a playlist"),
    ("2", "Generate ALL vibes at once"),
    ("3", "Genre playlists"),
    ("4", "Artist spotlight playlists"),
    ("5", "Era / decade playlists"),
    ("6", "Heavy Rotation (your most-played)"),
    ("7", "Taste report & stats"),
    ("r", "Refresh mining cache (re-scan public playlists)"),
    ("q", "Quit"),
]


def main():
    banner()

    section("CONNECTING TO SPOTIFY")
    print("  Opening browser for login (first time only)...")
    sp, me = connect()
    name = me.get("display_name") or me["id"]
    print(f"\n  Logged in as: {name}  ({me['id']})")

    section("LOADING YOUR LIBRARY")
    data = load_session(sp, me["id"])

    while True:
        section("MAIN MENU")
        moods_meta = all_moods()
        sorted_moods = sorted(data["mood_results"].items(), key=lambda x: -x[1]["cohesion"])

        print(f"\n  {len(data['all_tracks'])} songs · {len(data['mood_results'])} vibes discovered\n")
        for key, label in MENU:
            print(f"  [{key}] {label}")

        choice = ask("Choose").lower()

        if choice == "q":
            print("\n  Bye.\n")
            break
        elif choice == "1":
            action_pick_vibe(data)
        elif choice == "2":
            action_create_all_vibes(data)
        elif choice == "3":
            action_genre_playlists(data)
        elif choice == "4":
            action_artist_playlists(data)
        elif choice == "5":
            action_era_playlists(data)
        elif choice == "6":
            action_heavy_rotation(data)
        elif choice == "7":
            action_stats(data)
        elif choice == "r":
            import core.playlist_mining as pm
            if os.path.exists(pm.CACHE_PATH):
                os.remove(pm.CACHE_PATH)
            print("  Cache cleared. Restart to re-run mining.")
        else:
            print("  Unknown option.")


if __name__ == "__main__":
    main()
