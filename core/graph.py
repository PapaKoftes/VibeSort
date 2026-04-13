"""
core/graph.py — Anchor-seeded label propagation (the agreement layer).

Replaces the human-labeling signal that was lost when Spotify blocked
playlist_items in Development Mode.

OLD SYSTEM:  Human playlists → mined compound tags → scoring
NEW SYSTEM:  Graph clusters  → graph_mood_* tags  → scoring

The core insight is **agreement**: if multiple library tracks that are
musically similar to a known "Hollow" anchor all cluster together, their
shared similarity IS the signal.  No external playlist needed.

ALGORITHM
---------
1. Anchor injection
   Find library tracks that match entries in data/mood_anchors.json.
   These become seed nodes with confidence = 1.0.

2. Graph construction (BFS from seeds)
   For each seed, call Last.fm track.getSimilar, intersect results with
   library_lookup.  Keep edges where similarity >= min_similarity.
   Expand one more hop from those neighbours.

   Graph is undirected: if A→B then also B→A.
   All getSimilar results are cached permanently — no re-fetch.

3. Label propagation
   Standard weighted-mean formula:

     score(track, mood) = Σ(w_i × signal(neighbor_i, mood)) / Σ(w_i)

   where Σ is over ALL neighbours (including unlabelled ones, which
   contribute 0).  This is the "agreement" metric: a track needs
   MULTIPLE anchor-adjacent neighbours agreeing on a mood to score high.

   Applied for max_hops passes.  Each hop past the first is discounted
   by hop_decay so 2nd-hand label propagation produces weaker signal.

4. Tag conversion
   Each surviving label becomes a "graph_mood_<slug>" pseudo-tag at the
   propagated confidence score.  scorer.py treats these as high-confidence
   per-track signals (same tier as mood_* and anchor_*).

INTEGRATION
-----------
Inject graph tags into track_tags AFTER all enrichment, BEFORE scoring:

    graph_tags = run_graph_pipeline(tracks, api_key, mood_anchors,
                                    anchor_lookup, lfm_cache)
    for uri, tags in graph_tags.items():
        track_tags.setdefault(uri, {}).update(tags)

The graph_mood_* tags do NOT overwrite existing tags — they are additive.
"""

import re
from collections import defaultdict
from typing import Optional

_FEAT_PATTERN = re.compile(
    r"\s*[\(\[\{].*?[\)\]\}]|\s+feat\..*$|\s+ft\..*$",
    re.IGNORECASE,
)


def _clean(s: str) -> str:
    """Strip feat./parentheticals and normalise to lowercase."""
    return _FEAT_PATTERN.sub("", s).strip().lower()


def _slug(mood_name: str) -> str:
    """mood_name → snake_case slug (matches anchors.py normalisation)."""
    s = mood_name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


# ── Step 1: anchor injection ──────────────────────────────────────────────────

def inject_anchor_labels(tracks: list, anchor_lookup: dict) -> dict:
    """
    Find library tracks matching mood_anchors entries and assign mood labels.

    Args:
        tracks:        Full library track list (Spotify track dicts).
        anchor_lookup: {(artist_lower, clean_title_lower): [mood_name, ...]}
                       from anchors.build_anchor_lookup().

    Returns:
        seed_labels: {uri: {mood_slug: 1.0}}
        Only URIs that matched at least one anchor are included.
    """
    seed_labels: dict = {}
    for track in tracks:
        uri = track.get("uri", "")
        if not uri:
            continue
        artists = track.get("artists") or []
        title = _clean(track.get("name") or "")
        for art_obj in artists:
            artist = (art_obj.get("name") or "").lower().strip()
            mood_names = anchor_lookup.get((artist, title))
            if mood_names:
                if uri not in seed_labels:
                    seed_labels[uri] = {}
                for mood_name in mood_names:
                    seed_labels[uri][_slug(mood_name)] = 1.0
                break  # primary artist matched — stop
    return seed_labels


# ── Step 2: graph construction ────────────────────────────────────────────────

def build_similarity_graph(
    tracks: list,
    api_key: str,
    seed_labels: dict,
    cache: dict,
    min_similarity: float = 0.6,
    max_neighbors: int = 10,
    max_hops: int = 2,
) -> dict:
    """
    Build library-internal similarity graph via BFS from anchor seeds.

    Only calls track.getSimilar for tracks reachable from anchor seeds,
    which is vastly more efficient than calling for every library track
    while still covering the musically-relevant neighbourhood.

    Args:
        tracks:         Full library track list.
        api_key:        Last.fm API key.
        seed_labels:    {uri: {...}} — anchor seeds (BFS start nodes).
        cache:          Shared Last.fm cache dict (caller handles save).
        min_similarity: Minimum Last.fm match score to include an edge.
        max_neighbors:  Max outgoing edges per node.
        max_hops:       BFS depth (2 = anchor → neighbour → neighbour's neighbour).

    Returns:
        graph: {uri: [(neighbor_uri, similarity_weight), ...]}
        Edges are undirected (both directions stored), deduplicated,
        sorted descending by weight, and capped at max_neighbors.
    """
    from core import lastfm as _lf

    # Library lookup: (artist_lower, clean_title_lower) → uri
    lib_lookup: dict = {}
    uri_to_track: dict = {}
    for t in tracks:
        u = t.get("uri", "")
        if not u:
            continue
        artist = (((t.get("artists") or [{}])[0]) or {}).get("name", "")
        title = t.get("name", "")
        if artist and title:
            lib_lookup[(_clean(artist), _clean(title))] = u
        uri_to_track[u] = t

    # Bidirectional edge accumulator: {uri: {neighbor_uri: max_similarity}}
    raw_edges: dict = defaultdict(dict)

    visited: set = set()
    frontier: set = set(seed_labels.keys())

    for _hop in range(max_hops):
        next_frontier: set = set()

        for uri in frontier:
            if uri in visited:
                continue
            visited.add(uri)

            t = uri_to_track.get(uri)
            if not t:
                continue
            artist = (((t.get("artists") or [{}])[0]) or {}).get("name", "")
            title = t.get("name", "")
            if not (artist and title):
                continue

            neighbors = _lf.get_library_neighbors(
                artist, title, api_key,
                library_lookup=lib_lookup,
                limit=max_neighbors * 3,  # over-fetch, then filter
                cache=cache,
            )

            added = 0
            for nb_uri, sim in neighbors:
                if sim < min_similarity:
                    continue
                if added >= max_neighbors:
                    break
                # Store best similarity for each directed edge
                if sim > raw_edges[uri].get(nb_uri, 0.0):
                    raw_edges[uri][nb_uri] = sim
                # Reverse edge (undirected graph)
                if sim > raw_edges[nb_uri].get(uri, 0.0):
                    raw_edges[nb_uri][uri] = sim
                if nb_uri not in visited:
                    next_frontier.add(nb_uri)
                added += 1

        frontier = next_frontier
        if not frontier:
            break

    # Finalise: sort by weight desc, cap at max_neighbors
    graph: dict = {}
    for uri, nb_dict in raw_edges.items():
        edges = sorted(nb_dict.items(), key=lambda x: -x[1])[:max_neighbors]
        if edges:
            graph[uri] = edges

    return graph


# ── Step 3: label propagation ─────────────────────────────────────────────────

def propagate_labels(
    graph: dict,
    seed_labels: dict,
    max_hops: int = 2,
    hop_decay: float = 0.65,
    min_confidence: float = 0.15,
) -> dict:
    """
    Propagate mood labels from anchor seeds through the similarity graph.

    Formula (standard weighted-mean label propagation):

        score(track, mood) = Σ(w_i × signal(neighbor_i, mood)) / Σ(w_i)

    where Σ is over ALL neighbours.  Unlabelled neighbours contribute 0 to
    the numerator but positive weight to the denominator — this is the
    "agreement" mechanism.  A track needs MULTIPLE labelled neighbours
    agreeing on a mood to score meaningfully high.

    Successive hops apply hop_decay as an additional confidence discount
    to distinguish direct anchor adjacency from indirect propagation.

    Args:
        graph:          {uri: [(neighbor_uri, weight), ...]}
        seed_labels:    {uri: {mood_slug: 1.0}} — anchor ground truth.
        max_hops:       Propagation rounds.
        hop_decay:      Multiplier applied per hop past the first
                        (hop 1 → ×1.0, hop 2 → ×hop_decay, etc.)
        min_confidence: Minimum score to retain a label.

    Returns:
        labels: {uri: {mood_slug: confidence}}
        Includes anchor seeds at 1.0.
    """
    # Initialise with anchor labels (confidence = 1.0, never overwritten)
    labels: dict = {uri: dict(moods) for uri, moods in seed_labels.items()}

    for hop in range(max_hops):
        # hop 0 = direct anchor neighbours (no extra discount)
        # hop 1 = one more step away (discounted by hop_decay)
        decay = 1.0 if hop == 0 else hop_decay ** hop

        new_labels: dict = {}

        for uri, neighbors in graph.items():
            if not neighbors:
                continue

            total_weight = sum(w for _, w in neighbors)
            if total_weight <= 0:
                continue

            # Accumulate weighted mood signals from all neighbours
            mood_signal: dict = defaultdict(float)
            for nb_uri, w in neighbors:
                for mood_slug, conf in labels.get(nb_uri, {}).items():
                    mood_signal[mood_slug] += w * conf

            if not mood_signal:
                continue

            # Normalise, apply decay, filter
            hop_result: dict = {}
            for mood_slug, raw in mood_signal.items():
                conf = round((raw / total_weight) * decay, 4)
                if conf >= min_confidence:
                    hop_result[mood_slug] = conf

            if not hop_result:
                continue

            if uri in labels:
                # Already labelled (anchor or earlier hop) — only upgrade, never downgrade
                for mood_slug, conf in hop_result.items():
                    if conf > labels[uri].get(mood_slug, 0.0):
                        labels[uri][mood_slug] = conf
            else:
                new_labels[uri] = hop_result

        labels.update(new_labels)
        if not new_labels:
            break  # no new tracks labelled — graph exhausted

    return labels


# ── Step 4: tag conversion ────────────────────────────────────────────────────

def compute_graph_tags(propagated_labels: dict) -> dict:
    """
    Convert propagated mood labels → graph_mood_* pseudo-tags.

    Returns:
        {uri: {"graph_mood_<slug>": confidence, ...}}
    """
    result: dict = {}
    for uri, moods in propagated_labels.items():
        tags = {
            f"graph_mood_{slug}": conf
            for slug, conf in moods.items()
            if conf > 0
        }
        if tags:
            result[uri] = tags
    return result


# ── Full pipeline entry point ─────────────────────────────────────────────────

def run_graph_pipeline(
    tracks: list,
    api_key: str,
    anchor_lookup: dict,
    cache: dict,
    min_similarity: float = 0.6,
    max_neighbors: int = 10,
    max_hops: int = 2,
    hop_decay: float = 0.65,
    min_confidence: float = 0.15,
    progress_fn=None,
) -> dict:
    """
    Full graph pipeline: anchor injection → graph build → propagation → tags.

    Args:
        tracks:         Full library track list.
        api_key:        Last.fm API key.  Returns {} if empty.
        anchor_lookup:  {(artist_lower, clean_title_lower): [mood_name, ...]}
                        from anchors.build_anchor_lookup().
        cache:          Shared Last.fm cache dict (caller saves after return).
        min_similarity: Minimum similarity to include a graph edge (default 0.6).
        max_neighbors:  Max neighbours per node (default 10).
        max_hops:       BFS depth for graph + propagation rounds (default 2).
        hop_decay:      Per-hop confidence discount past hop 1 (default 0.65).
        min_confidence: Minimum confidence to retain a propagated label (0.15).
        progress_fn:    Optional callable(msg: str) for progress reporting.

    Returns:
        {uri: {"graph_mood_<slug>": confidence, ...}}
        Empty dict if no API key, no anchor matches, or no graph edges found.
    """
    def _log(msg: str) -> None:
        if progress_fn:
            progress_fn(msg)

    if not api_key:
        return {}

    if not anchor_lookup:
        return {}

    # ── 1. Anchor injection ───────────────────────────────────────────────────
    seed_labels = inject_anchor_labels(tracks, anchor_lookup)
    if not seed_labels:
        _log("Graph pipeline: no anchor tracks found in library")
        return {}
    _log(f"Graph: {len(seed_labels)} anchor tracks found in library")

    # ── 2. Graph construction (BFS from anchors) ──────────────────────────────
    graph = build_similarity_graph(
        tracks, api_key, seed_labels, cache,
        min_similarity=min_similarity,
        max_neighbors=max_neighbors,
        max_hops=max_hops,
    )
    total_edges = sum(len(v) for v in graph.values())
    _log(f"Graph: {len(graph)} nodes, {total_edges // 2} unique edges")

    if not graph:
        _log("Graph pipeline: no edges found (getSimilar returned no library matches)")
        return {}

    # ── 3. Label propagation ──────────────────────────────────────────────────
    propagated = propagate_labels(
        graph, seed_labels,
        max_hops=max_hops,
        hop_decay=hop_decay,
        min_confidence=min_confidence,
    )
    labeled_count = sum(1 for u in propagated if u not in seed_labels)
    _log(
        f"Graph: {labeled_count} non-anchor tracks labeled "
        f"({len(seed_labels)} anchors + {labeled_count} propagated)"
    )

    # ── 4. Tag conversion ─────────────────────────────────────────────────────
    return compute_graph_tags(propagated)
