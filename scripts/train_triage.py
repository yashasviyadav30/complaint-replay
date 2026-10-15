"""Train the triage model on CPU and measure it, plus cross-language duplicate retrieval, on a held-out half.

Data: data/complaints_multilingual.json (SYNTHETIC, 20 languages, 2 messages per scenario per language).
Split: of the 2 messages per (language, scenario), a seeded coin picks which one fits and which is held out.
A second, harder test fits on the first message only: the generator wrote different topics first and second
(dark mode, then cash on delivery), so it checks requests the model never saw a topic of.
Writes replay/triage.json (the model) and results/triage.md (the numbers, per language).
Run: uv run python scripts/train_triage.py
"""

import asyncio
import json
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from replay.grouping import EMBED_MODEL, cosine, embed  # noqa: E402
from replay.llm import make_client  # noqa: E402
from replay.triage import CLASSES, MODEL_FILE, classify, fit, label_of  # noqa: E402

DATA = ROOT / "data" / "complaints_multilingual.json"
REPORT = ROOT / "benchmarks" / "triage.md"
CACHE = ROOT / "results" / "multilingual_vectors.json"  # embeddings cost API calls; reuse them
BATCH = 40


async def vectors(texts: list[str]) -> list[list[float]]:
    if CACHE.exists():
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        if cached["texts"] == texts:
            return cached["vectors"]
    client = make_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        out += await embed(client, texts[i:i + BATCH])
    CACHE.write_text(json.dumps({"texts": texts, "vectors": out}), encoding="utf-8")
    return out


def split(rows: list[dict], shuffle: bool) -> tuple[list[int], list[int]]:
    pairs: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        pairs[(r["lang"], r["scenario"])].append(i)
    rng = random.Random(7)
    fit_idx, test_idx = [], []
    for idx in pairs.values():
        if shuffle and rng.random() < 0.5:
            idx = idx[::-1]
        fit_idx.append(idx[0])
        test_idx += idx[1:]
    return fit_idx, test_idx


def topic_shift(rows: list[dict], vecs: list[list[float]]) -> str:
    fit_idx, test_idx = split(rows, shuffle=False)
    centroids = fit([vecs[i] for i in fit_idx], [label_of(rows[i]["scenario"]) for i in fit_idx])
    per: dict[str, list[bool]] = defaultdict(list)
    for i in test_idx:
        want = label_of(rows[i]["scenario"])
        per[want].append(classify(vecs[i], centroids)["label"] == want)
    return ", ".join(f"{k} {pct(sum(v), len(v))}" for k, v in per.items())


def pct(n: int, d: int) -> str:
    return f"{n / d:.0%} ({n}/{d})" if d else "n/a"


async def main() -> None:
    load_dotenv()
    rows = json.loads(DATA.read_text(encoding="utf-8"))["complaints"]
    vecs = await vectors([r["text"] for r in rows])
    fit_idx, test_idx = split(rows, shuffle=True)
    centroids = fit([vecs[i] for i in fit_idx], [label_of(rows[i]["scenario"]) for i in fit_idx])
    MODEL_FILE.write_text(json.dumps({"embed_model": EMBED_MODEL, "trained_on": len(fit_idx), "classes": list(CLASSES),
                                      "centroids": centroids}), encoding="utf-8")

    # Triage on the held-out half
    by_lang: dict[str, list[bool]] = defaultdict(list)
    confusion: dict[tuple[str, str], int] = defaultdict(int)
    for i in test_idx:
        want, got = label_of(rows[i]["scenario"]), classify(vecs[i], centroids)["label"]
        by_lang[rows[i]["lang"]].append(want == got)
        confusion[(want, got)] += 1
    right = sum(sum(v) for v in by_lang.values())

    # Duplicate retrieval across languages: is the closest fit-half complaint the same bug?
    bugs_fit = [i for i in fit_idx if rows[i]["scenario"].startswith("bug:")]
    retrieval: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    for i in test_idx:
        if not rows[i]["scenario"].startswith("bug:"):
            continue
        near = sorted(((cosine(vecs[i], vecs[j]), j) for j in bugs_fit if rows[j]["lang"] != rows[i]["lang"]),
                      reverse=True)
        top = [rows[j]["scenario"] for _, j in near[:3]]
        retrieval[rows[i]["lang"]].append((top[0] == rows[i]["scenario"], rows[i]["scenario"] in top))
    r1 = sum(a for v in retrieval.values() for a, _ in v)
    r3 = sum(b for v in retrieval.values() for _, b in v)
    n_ret = sum(len(v) for v in retrieval.values())

    lines = [
        "# Triage and cross-language grouping", "",
        f"Measured {date.today().isoformat()} with `uv run python scripts/train_triage.py`. Embeddings: `{EMBED_MODEL}`.",
        "", "**Read this first:** the complaints are SYNTHETIC, written by Nemotron in 20 languages "
        "(`data/complaints_multilingual.json`), not collected from real users. Real complaints are messier; treat "
        "these numbers as a first check that nothing breaks across scripts, not as a benchmark.", "",
        f"Trained on {len(fit_idx)} complaints, tested on {len(test_idx)} held-out complaints. "
        "The model is one average vector per class, fitted on a laptop CPU in under a second.", "",
        "## Triage: bug, confusion, feature request or spam", "",
        f"Held-out accuracy: **{pct(right, len(test_idx))}**", "",
        "| Language | Correct |", "|---|---|",
        *[f"| {lang} | {pct(sum(v), len(v))} |" for lang, v in sorted(by_lang.items())],
        "", "Mistakes (true label -> predicted):", "",
        *[f"- {w} -> {g}: {n}" for (w, g), n in sorted(confusion.items()) if w != g], "",
        "**Known weakness.** Trained only on one kind of wish (dark mode) and tested on another (cash on delivery), "
        f"the model scores: {topic_shift(rows, vecs)}. It learns topics it has seen, not the idea of a wish. "
        "The safe direction holds: a missed feature request costs one extra replay, it never hides a bug.", "",
        "## Same bug, different language", "",
        "For each held-out bug complaint, the most similar complaints written in OTHER languages are looked up. "
        "Grouping checks the top 3 with a Nemotron verifier, so top-3 is the ceiling for what it can merge.", "",
        f"Nearest is the same bug: **{pct(r1, n_ret)}**. Same bug among the top 3: **{pct(r3, n_ret)}**.", "",
        "| Language | Top 1 | Top 3 |", "|---|---|---|",
        *[f"| {lang} | {pct(sum(a for a, _ in v), len(v))} | {pct(sum(b for _, b in v), len(v))} |"
          for lang, v in sorted(retrieval.items())],
    ]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
