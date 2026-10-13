"""Guard: a proven replay saved as a test that fails if the bug ever comes back.

A guard is plain JSON: the user's conditions, the steps by visible control name, and the evidence
kinds that must not appear. No model is needed to run it.
Run one: uv run python -m replay.guard guards/<id>.json http://127.0.0.1:8100
"""

import asyncio
import dataclasses
import json
import sys
from pathlib import Path

from replay.browser import Session
from replay.conditions import Condition


def build_guard(case_id: str, complaint: str, cond: Condition, steps: list[dict], kinds: set[str]) -> dict:
    """Keep only the steps that worked, addressed by the control's visible name rather than its position."""
    kept = []
    for s in steps:
        a = s["action"]
        if s["result"].startswith("error"):
            continue
        if a["type"] in ("click", "fill") and s.get("target"):
            extra = {"text": a["text"]} if a["type"] == "fill" else ({"times": a["times"]} if a.get("times") else {})
            kept.append({"do": a["type"], "label": s["target"], **extra})
        elif a["type"] in ("click_role", "fill_role"):
            kept.append({k: v for k, v in a.items() if k in ("role", "name", "text")} | {"do": a["type"]})
        elif a["type"] in ("wait", "scroll"):
            kept.append({"do": a["type"], **{k: v for k, v in a.items() if k in ("ms", "direction")}})
    return {"case": case_id, "complaint": complaint, "condition": dataclasses.asdict(cond),
            "must_not_see": sorted(kinds), "steps": kept}


async def run_guard(url: str, guard: dict) -> dict:
    cond = Condition(**guard["condition"])
    async with Session(url, cond) as session:
        for step in guard["steps"]:
            obs = await session.observe()
            action = {k: v for k, v in step.items() if k not in ("do", "label")} | {"type": step["do"]}
            if step["do"] in ("click", "fill"):
                match = next((e["idx"] for e in obs["elements"] if e["label"] == step["label"]), None)
                if match is None:
                    continue  # the control is gone or renamed; the evidence check below still decides
                action["target"] = match
            await session.act(action)
        await session.observe()
        hits = [e for e in session.evidence if e.kind in guard["must_not_see"]]
    return {"passed": not hits, "evidence": [{"kind": e.kind, "detail": e.detail} for e in hits]}


def main() -> None:
    guard = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = asyncio.run(run_guard(sys.argv[2], guard))
    print("PASS" if result["passed"] else f"FAIL: {result['evidence']}")
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
