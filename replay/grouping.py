"""Group duplicate complaints with NVIDIA's open embedding model and a threshold fitted on labelled data.

Forty people describe one bug forty ways ("OTP nahi aaya", "never got the code"). Grouping them means one
investigation per bug and a count of how many people it hurts. The settings live in grouping.json and are
tuned by scripts/calibrate_grouping.py on labelled data; nothing here is hand-tuned.
"""

import json
import math
import os
from pathlib import Path

from openai import AsyncOpenAI

from replay.llm import Chat, parse_json, throttle

EMBED_MODEL = os.getenv("EMBED_MODEL", "nvidia/nemotron-3-embed-1b")
SETTINGS = Path(__file__).with_name("grouping.json")
NORMALIZE_SYSTEM = """Rewrite the customer's complaint about an online shop as ONE short plain-English sentence that
states only the problem (what failed, where). Translate Hindi or Hinglish. No emotion, no apology.
Reply with ONE JSON object and nothing else: {"problem": "<sentence>"}"""
VERIFY_SYSTEM = """Two customers complained about the same online shop. Do they describe the same underlying problem?
Same symptom from the same cause counts; a different problem that merely sounds alike does not.
Reply with ONE JSON object and nothing else: {"same": true} or {"same": false}"""


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


async def embed(client: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    await throttle()
    resp = await client.embeddings.create(model=EMBED_MODEL, input=texts,
                                          extra_body={"input_type": "query", "truncate": "END"})
    return [d.embedding for d in resp.data]






def scores(pairs: list[tuple[float, bool]], thr: float) -> dict:
    tp = sum(1 for s, same in pairs if s >= thr and same)
    fp = sum(1 for s, same in pairs if s >= thr and not same)
    fn = sum(1 for s, same in pairs if s < thr and same)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3), "pairs": len(pairs)}






async def same_problem(chat: Chat, a: str, b: str) -> bool:
    reply = await chat([{"role": "system", "content": VERIFY_SYSTEM},
                        {"role": "user", "content": f"Complaint A: {a}\nComplaint B: {b}"}])
    try:
        return parse_json(reply).get("same") is True
    except ValueError:
        return False  # unreadable means "not proven the same": never merge on a guess


async def normalize(chat: Chat, text: str) -> str:
    """One plain-English problem sentence, so "otp nahi aa raha" and "never got the code" embed close together."""
    reply = await chat([{"role": "system", "content": NORMALIZE_SYSTEM}, {"role": "user", "content": text}])
    try:
        return str(parse_json(reply).get("problem") or text)
    except ValueError:
        return text


async def pick_verify_model(client: AsyncOpenAI) -> str:
    if os.getenv("VERIFY_MODEL"):
        return os.environ["VERIFY_MODEL"]
    ids = [m.id for m in (await client.models.list()).data]
    return next((m for m in ids if "nemotron" in m.lower() and "lightning" in m.lower()),
                os.getenv("REPLAY_MODEL", ""))


def settings() -> dict:
    """Tuned by scripts/calibrate_grouping.py: which text to embed and how many nearest cases to verify."""
    if SETTINGS.exists():
        s = json.loads(SETTINGS.read_text(encoding="utf-8"))
        if "top_k" in s:
            return {"embed_text": s["embed_text"], "top_k": s["top_k"]}
    return {"embed_text": "raw", "top_k": 3}


async def find_duplicate(client: AsyncOpenAI, text: str, vectors: dict[str, list[float]],
                         said: dict[str, str]) -> tuple[str | None, list[float]]:
    """Return (id of the open case this duplicates or None, this complaint's vector).

    The top-k most similar open cases (embedding) are each checked by Nemotron ("same problem?"); the first
    yes wins. A real shop has dozens of open cases, so verifying a few is cheap, and a fixed similarity cut
    proved fragile (Hinglish vs English duplicates scored only 0.2).
    """
    cfg = settings()
    chat = Chat(client, await pick_verify_model(client))
    source = await normalize(chat, text) if cfg["embed_text"] == "normalized" else text
    vec = (await embed(client, [source]))[0]
    nearest = sorted(((cosine(vec, v), cid) for cid, v in vectors.items() if cid in said), reverse=True)
    for _, cid in nearest[: cfg["top_k"]]:
        if await same_problem(chat, text, said[cid]):
            return cid, vec
    return None, vec
