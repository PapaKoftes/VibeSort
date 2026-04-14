"""
core/semantic_embed.py — Sentence-transformer embedding helpers.

Uses all-MiniLM-L6-v2 (already installed) to embed:
  • Track descriptors  → short text built from title + artist + tags
  • Mood definitions   → mood display name + expected_tags joined as prose

Cosine similarity is used to produce a [0, 1] semantic score.

Results are cached on disk so the model only runs once per unique input.

Public API
----------
embed_track(uri, title, artist, tags) → np.ndarray | None
embed_mood(mood_slug, display_name, expected_tags) → np.ndarray | None
semantic_score(track_vec, mood_vec) → float   # 0.0–1.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Cache directory ───────────────────────────────────────────────────────────
_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "cache", "semantic",
)
os.makedirs(_CACHE_DIR, exist_ok=True)

# ── Model singleton ───────────────────────────────────────────────────────────
_MODEL = None
_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model():
    """Load and cache the sentence-transformer model (lazy, once per process)."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _MODEL = SentenceTransformer(_MODEL_NAME)
        logger.debug("semantic_embed: model loaded (%s)", _MODEL_NAME)
    except Exception as exc:
        logger.warning("semantic_embed: could not load model — %s", exc)
        _MODEL = None
    return _MODEL


# ── Disk cache helpers ────────────────────────────────────────────────────────

def _cache_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _load_vec(key: str) -> Optional[np.ndarray]:
    path = os.path.join(_CACHE_DIR, f"{key}.npy")
    if os.path.exists(path):
        try:
            return np.load(path)
        except Exception:
            pass
    return None


def _save_vec(key: str, vec: np.ndarray) -> None:
    path = os.path.join(_CACHE_DIR, f"{key}.npy")
    try:
        np.save(path, vec)
    except Exception as exc:
        logger.debug("semantic_embed: could not save cache — %s", exc)


# ── Embedding functions ───────────────────────────────────────────────────────

def _embed_text(text: str) -> Optional[np.ndarray]:
    """Embed a string, returning a unit-normalised float32 array."""
    key = _cache_key(text)
    cached = _load_vec(key)
    if cached is not None:
        return cached

    model = _get_model()
    if model is None:
        return None

    try:
        vec = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        vec = np.array(vec, dtype=np.float32)
        _save_vec(key, vec)
        return vec
    except Exception as exc:
        logger.warning("semantic_embed: encode failed — %s", exc)
        return None


def embed_track(
    uri: str,
    title: str,
    artist: str,
    tags: Optional[dict] = None,
) -> Optional[np.ndarray]:
    """
    Build a short descriptor for a track and embed it.

    Format: "{title} by {artist}. Sounds {top_tags}."
    """
    parts = [f"{title} by {artist}."]
    if tags:
        # Pick top 5 tag names by weight, excluding meta/dz pseudo-tags
        _EXCLUDE_PREFIX = ("dz_", "meta_", "anchor_", "graph_mood_", "vader_", "lyr_")
        top = sorted(
            ((k, v) for k, v in tags.items() if not any(k.startswith(p) for p in _EXCLUDE_PREFIX)),
            key=lambda x: -float(x[1]),
        )[:5]
        if top:
            tag_str = ", ".join(t.replace("_", " ") for t, _ in top)
            parts.append(f"Sounds {tag_str}.")
    text = " ".join(parts)
    return _embed_text(text)


def embed_mood(
    mood_slug: str,
    display_name: str,
    expected_tags: Optional[list] = None,
) -> Optional[np.ndarray]:
    """
    Build a descriptor for a mood pack and embed it.

    Format: "{display_name}. Tags: {expected_tags prose}."
    """
    parts = [f"{display_name}."]
    if expected_tags:
        tag_str = ", ".join(str(t).replace("_", " ") for t in expected_tags[:10])
        parts.append(f"Tags: {tag_str}.")
    text = " ".join(parts)
    return _embed_text(text)


# ── Similarity ────────────────────────────────────────────────────────────────

def semantic_score(
    track_vec: Optional[np.ndarray],
    mood_vec: Optional[np.ndarray],
) -> float:
    """
    Cosine similarity between two unit-normalised vectors → [0, 1].

    Returns 0.0 if either vector is None (model not available or encode failed).
    """
    if track_vec is None or mood_vec is None:
        return 0.0
    try:
        sim = float(np.dot(track_vec, mood_vec))
        # Cosine similarity of unit vectors is in [-1, 1]; scale to [0, 1]
        return max(0.0, min(1.0, (sim + 1.0) / 2.0))
    except Exception:
        return 0.0


# ── Batch helpers ─────────────────────────────────────────────────────────────

def precompute_mood_vecs(packs: dict) -> dict[str, Optional[np.ndarray]]:
    """
    Pre-embed all mood packs from packs.json data.

    packs: dict mapping mood_slug → pack definition dict
    Returns: dict mood_slug → np.ndarray | None
    """
    from core.mood_graph import mood_display_name  # local import to avoid circular

    result: dict[str, Optional[np.ndarray]] = {}
    for slug, pack in packs.items():
        dname = mood_display_name(slug)
        tags = pack.get("expected_tags", [])
        result[slug] = embed_mood(slug, dname, tags)
    return result


def is_available() -> bool:
    """Return True if the sentence-transformer model can be loaded."""
    return _get_model() is not None
