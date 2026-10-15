"""One planted bug, end to end from the command line: reproduce -> fix -> prove.

Run: uv run python pipeline.py 1     (bug id from replay/bugs.py)
Writes results/cases/bug-<id>.json, the same case format the dashboard shows.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from replay.bugs import BUGS_BY_ID, inject, reset_workspace
from replay.conditions import CONDITIONS
from replay.investigate import investigate
from replay.llm import Chat, make_client, pick_model
from replay.shop import running_shop

CASES_DIR = Path(__file__).parent / "results" / "cases"


def save(case: dict) -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    (CASES_DIR / f"{case['id']}.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")


async def run_bug(bug_id: int) -> dict:
    bug = BUGS_BY_ID[bug_id]
    cond = CONDITIONS[bug.condition]
    client = make_client()
    chat = Chat(client, await pick_model(client))
    case = {"id": f"bug-{bug_id}", "created_at": datetime.now(timezone.utc).isoformat(), "kind": "spoken",
            "complaint": bug.complaint, "condition": {"label": cond.label, "persona": cond.persona}, "stage": "heard"}
    shop = reset_workspace()
    inject(bug, shop)
    with running_shop(shop) as url:
        return await investigate(case, cond, url, shop, client, chat, save, CASES_DIR / "shots")


def main() -> None:
    load_dotenv()
    sys.stdout.reconfigure(encoding="utf-8")  # model text can hold characters the Windows console code page lacks
    case =asyncio.run(run_bug(int(sys.argv[1]) if len(sys.argv) > 1 else 1))
    print(f"{case['id']}: stage={case['stage']}  verdict={case['replay']['verdict']}")
    if "fix" in case:
        print(f"Fix ({case['fix']['model']}): {case['fix'].get('explanation') or case['fix'].get('error')}")
        print(case["fix"].get("diff", ""))
    if "proof" in case:
        print(f"Proof replay: {case['proof']['verdict']}")


if __name__ == "__main__":
    main()
