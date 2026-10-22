"""Repeat every planted bug through the full chain and report real success rates.

Run: uv run python scripts/bench_demo.py 3      (runs per bug; writes results/bench.json and results/bench.md)
Also replays each bug's complaint on the clean shop to count false alarms.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from run_bug import run_bug  # noqa: E402
from replay.agent import replay  # noqa: E402
from replay.bugs import BUGS, reset_workspace  # noqa: E402
from replay.conditions import CONDITIONS  # noqa: E402
from replay.llm import Chat, llm_matcher, llm_policy, make_client, pick_model  # noqa: E402
from replay.project import running_app  # noqa: E402

OUT = ROOT / "results"
DEPTH = {"reproduced": 1, "fixing": 1, "proving": 1, "fix_unproven": 1, "fix_failed": 1, "fixed": 2, "guarded": 3}


async def clean_run(bug, chat: Chat) -> str:
    shop = reset_workspace()
    with running_app(shop) as url:
        r = await replay(url, bug.complaint, CONDITIONS[bug.condition], llm_policy(chat), llm_matcher(chat))
    return r.verdict


async def main(runs: int) -> None:
    load_dotenv()
    client = make_client()
    chat = Chat(client, await pick_model(client))
    rows = []
    for bug in BUGS:
        stages, seconds = [], []
        for _ in range(runs):
            started = time.monotonic()
            case = await run_bug(bug.id)
            seconds.append(round(time.monotonic() - started))
            stages.append(case["stage"])
        depth = [DEPTH.get(s, 0) for s in stages]
        row = {
            "bug": bug.id, "title": bug.title, "condition": bug.condition, "runs": runs, "stages": stages,
            "reproduced": sum(d >= 1 for d in depth), "fixed": sum(d >= 2 for d in depth),
            "guarded": sum(d >= 3 for d in depth),
            "false_alarm_on_clean": (await clean_run(bug, chat)) == "reproduced",
            "median_seconds": sorted(seconds)[len(seconds) // 2],
        }
        rows.append(row)
        print(f"bug {bug.id:>2}: {stages} false_alarm={row['false_alarm_on_clean']}", flush=True)

    OUT.mkdir(exist_ok=True)
    (OUT / "bench.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = ["| Bug | User condition | Reproduced | Fixed + proven | Guarded | False alarm on clean shop | Median time |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['title']} | {CONDITIONS[r['condition']].label} | {r['reproduced']}/{r['runs']} | "
                     f"{r['fixed']}/{r['runs']} | {r['guarded']}/{r['runs']} | "
                     f"{'yes' if r['false_alarm_on_clean'] else 'no'} | {r['median_seconds']} s |")
    (OUT / "bench.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
