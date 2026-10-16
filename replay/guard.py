"""Guard: a proven replay saved as a test that fails if the bug ever comes back.

A guard is plain JSON: the user's conditions, the steps by visible control name, and the evidence
evidence that must not appear (kind + detail, numbers blanked). No model is needed to run it.
Run one: uv run python -m replay.guard guards/<id>.json http://127.0.0.1:8100
"""

import asyncio
import dataclasses
import json
import sys
from pathlib import Path

from replay.browser import Session, evidence_key
from replay.conditions import Condition


def build_guard(case_id: str, complaint: str, cond: Condition, steps: list[dict], keys: set[str]) -> dict:
    """Keep only the steps that worked, addressed by the control's visible name rather than its position."""
    kept = []
    for s in steps:
        a = s["action"]
        if s["result"].startswith("error"):
            continue
        # "idx" is the control's position on the page: the fallback when a fix renames it (an added aria-label).
        position = {"idx": s["idx"]} if s.get("idx") is not None else {}
        if a["type"] in ("click", "fill") and s.get("target"):
            extra = {"text": a["text"]} if a["type"] == "fill" else ({"times": a["times"]} if a.get("times") else {})
            kept.append({"do": a["type"], "label": s["target"], **extra, **position})
        elif a["type"] in ("click_role", "fill_role"):
            kept.append({k: v for k, v in a.items() if k in ("role", "name", "text")} | {"do": a["type"], **position})
        elif a["type"] in ("wait", "scroll", "press", "type", "goto"):
            keep = ("ms", "direction", "key", "text", "path")
            kept.append({"do": a["type"], **{k: v for k, v in a.items() if k in keep}})
    return {"case": case_id, "complaint": complaint, "condition": dataclasses.asdict(cond),
            "must_not_see": sorted(keys), "steps": kept}


async def run_guard(url: str, guard: dict, storage_state: Path | None = None, screenshot: Path | None = None,
                    checks: dict[str, str] | None = None) -> dict:
    cond = Condition(**guard["condition"])
    async with Session(url, cond, storage_state, checks) as session:
        for step in guard["steps"]:
            obs = await session.observe()
            action = {k: v for k, v in step.items() if k not in ("do", "label", "idx")} | {"type": step["do"]}
            on_page = {e["idx"] for e in obs["elements"]}
            if step["do"] in ("click", "fill"):
                match = next((e["idx"] for e in obs["elements"] if e["label"] == step["label"]), None)
                if match is None and step.get("idx") in on_page:
                    match = step["idx"]  # renamed by the fix: same control, same place
                if match is None:
                    continue  # the control is gone; the evidence check below still decides
                action["target"] = match
            elif step["do"] in ("click_role", "fill_role") and step.get("idx") in on_page:
                found = await session.page.get_by_role(step["role"], name=step["name"]).count()
                if not found:
                    action = {"type": step["do"].removesuffix("_role"), "target": step["idx"],
                              **({"text": step["text"]} if "text" in step else {})}
            await session.act(action)
        await session.observe()
        if screenshot:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            await session.page.screenshot(path=str(screenshot))
        banned = set(guard["must_not_see"])  # evidence keys; older guards list bare kinds
        hits = [e for e in session.evidence if evidence_key(e.kind, e.detail) in banned or e.kind in banned]
    return {"passed": not hits, "evidence": [{"kind": e.kind, "detail": e.detail} for e in hits]}


async def run_all(url: str, guards: list[Path], storage_state: Path | None = None,
                  checks: dict[str, str] | None = None) -> dict[str, dict]:
    """Every guard against one running app: {guard file name: result}."""
    results = {}
    for path in guards:
        results[path.name] = await run_guard(url, json.loads(path.read_text(encoding="utf-8")), storage_state, checks=checks)
    return results


def main() -> None:
    guard = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = asyncio.run(run_guard(sys.argv[2], guard))
    print("PASS" if result["passed"] else f"FAIL: {result['evidence']}")
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
