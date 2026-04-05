"""
train_weights.py — Aggregate local telemetry into outputs/.user_model.json.

Run: python -m ml.train_weights

Uses:
  • deploy_playlist events → tag_biases (existing)
  • mood_feedback events → score_weights nudges (tags vs semantic vs genre)

Log feedback from code:
  from core.telemetry import log_event
  log_event("mood_feedback", mood="Hollow", rating=1)   # liked
  log_event("mood_feedback", mood="Drill", rating=-1)  # poor fit

Never log API secrets. Keys stay in .env only.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUT = os.path.join(_ROOT, "outputs", ".user_model.json")

from ml.dataset import load_events


def _tokens_from_name(name: str) -> list[str]:
    return [t for t in re.split(r"[^\w]+", name.lower()) if len(t) > 2]


def _clamp_weights(wt: float, ws: float, wg: float) -> dict[str, float]:
    """Clamp each dimension then renormalise to 1.0 (audio slot stays 0 in config; proxy handled in scorer)."""
    wt = max(0.34, min(0.58, wt))
    ws = max(0.18, min(0.36, ws))
    wg = max(0.10, min(0.28, wg))
    s = wt + ws + wg
    if s <= 0:
        return {"w_tags": 0.46, "w_semantic": 0.26, "w_genre": 0.18, "w_audio": 0.0}
    return {
        "w_tags": round(wt / s, 4),
        "w_semantic": round(ws / s, 4),
        "w_genre": round(wg / s, 4),
        "w_audio": 0.0,
    }


def main() -> None:
    events = load_events()
    deploys = [e for e in events if e.get("event") == "deploy_playlist"]
    feedback = [e for e in events if e.get("event") == "mood_feedback" and e.get("rating") is not None]

    model: dict = {"version": 2}

    if len(deploys) >= 3:
        counts: Counter[str] = Counter()
        for e in deploys:
            name = e.get("playlist_name") or e.get("name") or ""
            for tok in _tokens_from_name(str(name)):
                counts[tok] += 1
        max_c = max(counts.values()) or 1
        tag_biases: dict[str, float] = {}
        for tok, c in counts.most_common(40):
            tag_biases[tok] = round(0.02 * (c / max_c), 4)
        model["tag_biases"] = tag_biases
        model["n_deploys"] = len(deploys)
        print(f"Tag biases from {len(deploys)} deploy_playlist events.")

    if len(feedback) >= 8:
        pos = sum(1 for e in feedback if float(e.get("rating", 0)) > 0)
        ratio = pos / len(feedback)
        # Users who mostly like results → trust tags/mining vocabulary a bit more.
        # Mixed/negative → lean on semantic + genre structure.
        base_t, base_s, base_g = 0.46, 0.26, 0.18
        if ratio >= 0.72:
            adj_t, adj_s, adj_g = 0.03, 0.0, -0.02
        elif ratio <= 0.42:
            adj_t, adj_s, adj_g = -0.04, 0.04, 0.02
        else:
            adj_t, adj_s, adj_g = 0.0, 0.0, 0.0
        model["score_weights"] = _clamp_weights(base_t + adj_t, base_s + adj_s, base_g + adj_g)
        model["n_mood_feedback"] = len(feedback)
        print(
            f"score_weights from {len(feedback)} mood_feedback events "
            f"(positive ratio {ratio:.2f})."
        )
    elif feedback:
        print(f"mood_feedback: have {len(feedback)} events; need 8+ to tune score_weights.")

    if len(model) <= 1:
        print("No training output (need deploy_playlist≥3 and/or mood_feedback≥8).")
        return

    prev: dict = {}
    if os.path.exists(_OUT):
        try:
            with open(_OUT, encoding="utf-8") as f:
                prev = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    if isinstance(prev, dict):
        if "tag_biases" not in model and prev.get("tag_biases"):
            model["tag_biases"] = prev["tag_biases"]
        if "score_weights" not in model and prev.get("score_weights"):
            model["score_weights"] = prev["score_weights"]
        if "n_deploys" not in model and prev.get("n_deploys") is not None:
            model["n_deploys"] = prev["n_deploys"]

    os.makedirs(os.path.dirname(_OUT), exist_ok=True)
    with open(_OUT, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2)
    print(f"Wrote {_OUT}")


if __name__ == "__main__":
    main()
