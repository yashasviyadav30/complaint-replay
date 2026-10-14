"""Tune duplicate grouping on half of the labelled complaints, then measure it on the other half.

The measurement simulates the real job: complaints arrive one by one; each is checked against the top-k most
similar open cases (embedding similarity) and Nemotron confirms "same problem" before it joins one.
Settings tried: top_k in {1, 3}, embedding of the raw text or of a normalised English problem sentence.
Run: uv run python scripts/calibrate_grouping.py      -> replay/grouping.json
"""

import asyncio
import itertools
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from replay.grouping import (EMBED_MODEL, SETTINGS, cosine, embed, normalize,  # noqa: E402
                             pick_verify_model, same_problem, scores)
from replay.llm import Chat, make_client  # noqa: E402

DATA = ROOT / "data" / "complaints_labeled.json"
CONFIGS = [(text, k) for text in ("raw", "normalized") for k in (1, 3)]


def split(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Alternate within each label, so both halves hold every bug and unrelated complaints."""
    fit, test = [], []
    by_label: dict = {}
    for item in items:
        by_label.setdefault(item["bug"], []).append(item)
    for group in by_label.values():
        fit += group[0::2]
        test += group[1::2]
    return fit, test


async def simulate(items: list[dict], vec_key: str, k: int, chat: Chat) -> dict:
    """Group complaints in arrival order; score every pair (same predicted group vs same labelled bug)."""
    groups: list[dict] = []  # {"vec", "text", "members"}
    calls = 0
    for item in items:
        nearest = sorted(groups, key=lambda g: cosine(item[vec_key], g["vec"]), reverse=True)[:k]
        for group in nearest:
            calls += 1
            if await same_problem(chat, item["text"], group["text"]):
                group["members"].append(item)
                break
        else:
            groups.append({"vec": item[vec_key], "text": item["text"], "members": [item]})
    group_of = {id(m): gi for gi, g in enumerate(groups) for m in g["members"]}
    pairs = [(1.0 if group_of[id(a)] == group_of[id(b)] else 0.0, a["bug"] is not None and a["bug"] == b["bug"])
             for a, b in itertools.combinations(items, 2)]
    return scores(pairs, 0.5) | {"verifier_calls": calls, "groups": len(groups)}


async def main() -> None:
    load_dotenv(ROOT / ".env")
    items = json.loads(DATA.read_text(encoding="utf-8"))["complaints"]
    client = make_client()
    chat = Chat(client, await pick_verify_model(client))
    problems = [await normalize(chat, i["text"]) for i in items]
    raw_vecs = await embed(client, [i["text"] for i in items])
    norm_vecs = await embed(client, problems)
    for item, r, n in zip(items, raw_vecs, norm_vecs):
        item["raw"], item["normalized"] = r, n
    fit, test = split(items)

    tried = {}
    for text, k in CONFIGS:
        tried[f"{text}/top{k}"] = await simulate(fit, text, k, chat)
        print(f"fit {text}/top{k}: {tried[f'{text}/top{k}']}", flush=True)
    # Best F1 on the fitting half; ties go to fewer verifier calls (cheaper).
    best = max(tried, key=lambda key: (tried[key]["f1"], -tried[key]["verifier_calls"]))
    text, k = best.split("/top")[0], int(best.split("/top")[1])
    result = {"embed_model": EMBED_MODEL, "verifier_model": chat.model, "embed_text": text, "top_k": k,
              "fit_tried": tried, "test": await simulate(test, text, k, chat),
              "complaints": {"fit": len(fit), "test": len(test)}, "measured_on": date.today().isoformat()}
    SETTINGS.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("embed_text", "top_k", "test")}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
