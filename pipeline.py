"""One complaint, end to end: replay -> fix -> prove.

Run: uv run python pipeline.py 1     (bug id from replay/bugs.py)
Writes results/cases/bug-<id>.json, which the dashboard will read.
"""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from replay.agent import ReplayResult, replay
from replay.bugs import BUGS_BY_ID, inject, reset_workspace
from replay.conditions import CONDITIONS
from replay.fix import apply_patch, pick_fix_model, propose_fix
from replay.llm import Chat, llm_matcher, llm_policy, make_client, pick_model
from replay.shop import running_shop

CASES_DIR = Path(__file__).parent / "results" / "cases"


def as_dict(r: ReplayResult) -> dict:
    return {
        "verdict": r.verdict, "summary": r.summary, "cited": list(r.cited),
        "evidence": [{"id": e.id, "kind": e.kind, "detail": e.detail, "step": e.step} for e in r.evidence],
        "steps": list(r.steps),
    }


def fix_proven(before: ReplayResult, after: ReplayResult) -> bool:
    """Proven = the same user no longer reproduces it, and the evidence kinds that proved the bug are gone."""
    proof_kinds = {e.kind for e in before.evidence if e.id in before.cited}
    return after.verdict != "reproduced" and not proof_kinds & {e.kind for e in after.evidence}


async def run_case(bug_id: int) -> dict:
    bug = BUGS_BY_ID[bug_id]
    cond = CONDITIONS[bug.condition]
    client = make_client()
    chat = Chat(client, await pick_model(client))
    policy, matcher = llm_policy(chat), llm_matcher(chat)
    case = {"bug": bug_id, "complaint": bug.complaint, "condition": cond.label, "stage": "heard"}

    shop = reset_workspace()
    inject(bug, shop)
    with running_shop(shop) as url:
        before = await replay(url, bug.complaint, cond, policy, matcher)
    case["replay"] = as_dict(before)
    if before.verdict != "reproduced":
        return case
    case["stage"] = "reproduced"

    fix_model = await pick_fix_model(client)
    patch = await propose_fix(client, fix_model, bug.complaint, cond, before, shop)
    try:
        diff = apply_patch(patch, shop)
    except ValueError as e:
        case["fix"] = {"model": fix_model, "explanation": patch.explanation, "error": str(e)}
        return case
    case["fix"] = {"model": fix_model, "explanation": patch.explanation, "diff": diff}

    with running_shop(shop) as url:  # restart: backend fixes need a fresh server
        after = await replay(url, bug.complaint, cond, policy, matcher)
    case["proof"] = as_dict(after)
    if fix_proven(before, after):
        case["stage"] = "fixed"
    return case


def main() -> None:
    load_dotenv()
    bug_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    case = asyncio.run(run_case(bug_id))
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    out = CASES_DIR / f"bug-{bug_id}.json"
    out.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Bug {bug_id}: stage={case['stage']}  verdict={case['replay']['verdict']}")
    if "fix" in case:
        print(f"Fix ({case['fix']['model']}): {case['fix'].get('explanation') or case['fix'].get('error')}")
        print(case["fix"].get("diff", ""))
    if "proof" in case:
        print(f"Proof replay: {case['proof']['verdict']}")
    print(f"Case file: {out}")


if __name__ == "__main__":
    main()
