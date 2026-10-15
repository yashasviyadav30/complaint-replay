"""Is a complaint a bug worth replaying, or a feature wish, plain confusion, or spam?

A tiny model trained on a laptop CPU, no GPU: one average Nemotron Embed vector per class (nearest centroid),
fitted by scripts/train_triage.py on labelled complaints in 20 languages. It reuses the vector duplicate
grouping already computed, so it costs no extra model call.
"""

import json
import math
from functools import cache
from pathlib import Path

MODEL_FILE = Path(__file__).with_name("triage.json")
CLASSES = ("bug", "ux_confusion", "feature_request", "spam")
SKIP_MARGIN = 0.05  # only skip a replay when "not a bug" wins clearly


def label_of(scenario: str) -> str:
    return "bug" if scenario.startswith("bug:") else scenario


def unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def fit(vectors: list[list[float]], labels: list[str]) -> dict[str, list[float]]:
    """One centroid per class: the mean of its unit vectors."""
    centroids = {}
    for c in CLASSES:
        rows = [unit(v) for v, lab in zip(vectors, labels) if lab == c]
        if rows:
            centroids[c] = unit([sum(col) / len(rows) for col in zip(*rows)])
    return centroids


def ranked(vec: list[float], centroids: dict[str, list[float]]) -> list[tuple[float, str]]:
    u = unit(vec)
    return sorted(((sum(a * b for a, b in zip(u, c)), name) for name, c in centroids.items()), reverse=True)


@cache
def load() -> dict[str, list[float]]:
    return json.loads(MODEL_FILE.read_text(encoding="utf-8"))["centroids"] if MODEL_FILE.exists() else {}


def classify(vec: list[float], centroids: dict[str, list[float]] | None = None) -> dict:
    """{"label", "margin" over the runner-up, "replay": whether a replay is worth spending on it}."""
    centroids = centroids or load()
    if not centroids:
        return {"label": "bug", "margin": 0.0, "replay": True}
    top = ranked(vec, centroids)
    margin = top[0][0] - top[1][0] if len(top) > 1 else 1.0
    label = top[0][1]
    return {"label": label, "margin": round(margin, 3),
            "replay": label in ("bug", "ux_confusion") or margin < SKIP_MARGIN}
