"""
features.py — Deterministic feature vectors from Vibesort track profiles.

Used for offline experiments and simple sklearn models (see train_weights.py).
"""

from __future__ import annotations

import numpy as np


def profile_to_feature_vector(profile: dict, tag_vocab: list[str] | None = None) -> np.ndarray:
    """
    Fixed-size vector: [audio_vector (6)] + [one-hot or bag tags].

    If tag_vocab is None, returns only the 6-dim audio_vector (zeros if missing).
    """
    av = profile.get("audio_vector") or [0.5] * 6
    base = np.array([float(x) for x in av[:6]], dtype=np.float64)
    if not tag_vocab:
        return base
    tags = profile.get("tags") or {}
    bag = np.zeros(len(tag_vocab), dtype=np.float64)
    for i, t in enumerate(tag_vocab):
        bag[i] = float(tags.get(t, 0.0))
    return np.concatenate([base, bag])
