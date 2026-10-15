"""Day-3 kill switch: can Nemotron reproduce planted bugs from complaint text alone?

Pass rule: at least 3 of 5 bugs reproduced, and no false "reproduced" on the clean shop.
Run: uv run python risk_test.py  (needs NEBIUS_API_KEY in .env)
"""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from replay.agent import replay
from replay.bugs import BUGS, inject, reset_workspace
from replay.conditions import CONDITIONS
from replay.llm import Chat, llm_matcher, llm_policy, make_client, pick_model
from replay.project import running_app

RESULTS = Path(__file__).parent / "results" / "risk_test.json"
PASS_MIN_REPRODUCED = 3


async def run_one(bug, buggy: bool, policy, matcher) -> dict:
    shop = reset_workspace()
    if buggy:
        inject(bug, shop)
    with running_app(shop) as url:
        r = await replay(url, bug.complaint, CONDITIONS[bug.condition], policy, matcher)
    return {
        "verdict": r.verdict, "summary": r.summary, "cited": list(r.cited), "steps": list(r.steps),
        "evidence": [{"id": e.id, "kind": e.kind, "detail": e.detail} for e in r.evidence],
    }


async def main() -> None:
    load_dotenv()
    client = make_client()
    model = await pick_model(client)
    chat = Chat(client, model)
    policy, matcher = llm_policy(chat), llm_matcher(chat)
    print(f"Model: {model}\n")
    rows = []
    for bug in BUGS:
        buggy = await run_one(bug, True, policy, matcher)
        clean = await run_one(bug, False, policy, matcher)
        rows.append({"bug": bug.id, "title": bug.title, "condition": bug.condition, "buggy": buggy, "clean": clean})
        print(f"Bug {bug.id:>2} [{bug.condition}] buggy={buggy['verdict']:<15} clean={clean['verdict']:<15} {bug.title}")

    reproduced = sum(r["buggy"]["verdict"] == "reproduced" for r in rows)
    false_alarms = sum(r["clean"]["verdict"] == "reproduced" for r in rows)
    passed = reproduced >= PASS_MIN_REPRODUCED and false_alarms == 0
    print(f"\nReproduced {reproduced}/{len(rows)}, false alarms {false_alarms}. {'PASS' if passed else 'FAIL'}")
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps({"model": model, "passed": passed, "rows": rows}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"Details: {RESULTS}")


if __name__ == "__main__":
    asyncio.run(main())
