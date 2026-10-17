"""Benchmark on real bugs: re-create each one by reverse-applying its real upstream fix, then run the whole chain.

Usage: uv run python scripts/bench_real.py <path to the app's git checkout> [pr ...]
       uv run python scripts/bench_real.py --report     (rebuild the table from saved results)
In CI: .github/workflows/real-bugs.yml runs one job per bug.
Cases: benchmarks/real-bugs.json. Results: benchmarks/real-bugs.md (every case, misses included) and
results/real-bugs/<pr>.json (the full case: evidence, steps, fix, guard).
The checkout's files are restored after each case, whatever happens.
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from replay.conditions import profile  # noqa: E402
from replay.investigate import investigate  # noqa: E402
from replay.llm import Chat, make_client, pick_model  # noqa: E402
from replay.project import running_app  # noqa: E402

CASES = ROOT / "benchmarks" / "real-bugs.json"
REPORT = ROOT / "benchmarks" / "real-bugs.md"
OUT = ROOT / "results" / "real-bugs"
CASE_TIMEOUT_S = 80 * 60  # two fix rounds on a free, slow endpoint: case 8733 ran out at 45 min (run 10)
NOT_SOURCE = ("test", "e2e", "stories", "upcoming-release-notes", "__snapshots__")


def git(repo: Path, *args: str, stdin: str | None = None) -> str:
    # Bytes, not text: on Windows, text mode turns a patch's \n into \r\n and `git apply` rejects it.
    out = subprocess.run(["git", *args], cwd=repo, input=stdin.encode("utf-8") if stdin else None,
                         capture_output=True, check=True).stdout
    return out.decode("utf-8")


def fix_files(repo: Path, commit: str) -> list[str]:
    return [f for f in git(repo, "show", "--name-only", "--format=", commit).split() if not any(w in f for w in NOT_SOURCE)]


def unfix(repo: Path, commit: str, files: list[str]) -> None:
    """Put the bug back: the real fix, applied in reverse to today's code."""
    git(repo, "apply", "-R", stdin=git(repo, "show", commit, "--", *files))


def restore(repo: Path, files: list[str]) -> None:
    git(repo, "checkout", "HEAD", "--", *files)


def edited_files(case: dict) -> list[str]:
    return sorted({e.get("file", "") for e in (case.get("fix") or {}).get("edits", [])})


async def run_case(repo: Path, spec: dict, client, chat) -> dict:
    user = spec["user"]
    cond = profile(user.get("device", ""), keyboard_only=bool(user.get("keyboard")), max_steps=25)
    case = {"id": f"pr{spec['pr']}", "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "kind": "spoken",
            "complaint": spec["complaint"], "said": spec["complaint"],
            "condition": {"label": cond.label, "persona": cond.persona}, "stage": "heard"}
    OUT.mkdir(parents=True, exist_ok=True)

    def save(c: dict) -> None:
        (OUT / f"{c['id']}.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  pr{spec['pr']}: {c['stage']}", flush=True)

    with running_app(repo) as url:
        return await asyncio.wait_for(investigate(case, cond, url, repo, client, chat, save, OUT / "shots"),
                                      CASE_TIMEOUT_S)


def row(spec: dict, case: dict, real: list[str], seconds: float) -> str:
    stage = case.get("stage", "error")
    ours = edited_files(case)
    same = "yes" if ours and set(ours) & set(real) else ("no" if ours else "")
    solved = "**yes**" if stage in ("guarded", "fixed") and same == "yes" else "no"
    rep = case.get("replay") or {}
    cited = [e["kind"] for e in rep.get("evidence", []) if e["id"] in rep.get("cited", [])]
    return (f"| [#{spec['pr']}](https://github.com/actualbudget/actual/pull/{spec['pr']}) | {spec['complaint'][:70]}… | "
            f"{case['condition']['label']} | {stage} | {', '.join(cited) or '-'} | {same} | {solved} | {seconds / 60:.0f} min |")


async def main() -> None:
    load_dotenv(ROOT / ".env")
    repo = Path(sys.argv[1]).resolve()
    wanted = {int(a) for a in sys.argv[2:]}
    specs = [s for s in json.loads(CASES.read_text(encoding="utf-8"))["cases"] if not wanted or s["pr"] in wanted]
    client = make_client()
    chat = Chat(client, await pick_model(client))
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        files = fix_files(repo, spec["commit"])
        started = time.monotonic()
        print(f"pr{spec['pr']}: re-creating the bug in {', '.join(files)}", flush=True)
        try:
            unfix(repo, spec["commit"], files)
            case = await run_case(repo, spec, client, chat)
        except Exception as e:  # a crash is a result too: it goes in the table
            case = {"stage": "error", "error": str(e)[:300], "condition": {"label": spec["user"].get("device", "desktop")}}
            print(f"  pr{spec['pr']}: error {e!r}", flush=True)
        finally:
            restore(repo, files)
        case["bench"] = {"real_files": files, "seconds": round(time.monotonic() - started), "model": chat.model}
        (OUT / f"pr{spec['pr']}.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(repo)


def write_report(repo: Path | None) -> None:
    """Every case in the cases file that has a saved result, so re-running a few cases updates only their rows."""
    rows, model = [], ""
    for spec in json.loads(CASES.read_text(encoding="utf-8"))["cases"]:
        saved = OUT / f"pr{spec['pr']}.json"
        if not saved.exists():
            continue
        case = json.loads(saved.read_text(encoding="utf-8"))
        bench = case.get("bench", {})
        model = bench.get("model", model)
        real = bench.get("real_files") or (fix_files(repo, spec["commit"]) if repo else [])  # older results
        rows.append(row(spec, case, real, bench.get("seconds", 0)))
    REPORT.write_text("\n".join([
        "# Real bugs: Actual Budget", "",
        f"Measured {time.strftime('%Y-%m-%d')} with `uv run python scripts/bench_real.py <actual checkout>`, model "
        f"`{model}`. Each bug was fixed upstream; it is re-created by reverse-applying that fix to today's code, "
        "and the complaint is written from the real report. \"Same file\" means our fix edited a file the real fix "
        "edited. Every case is listed, misses included.", "",
        f"**Solved {sum('**yes**' in r for r in rows)} of {len(rows)}.** Solved means fixed and guarded AND our fix edited "
        "a file the real fix edited. A \"fixed\" with a different file is counted as a miss: the guard may have "
        "proven the wrong thing.", "",
        # A second, looser number, defined before it is read: the guard (the user's own steps, replayed by code)
        # passes on our fix and fails on the bug, whatever file the fix is in. The diff is in each case's result.
        f"**Fixed and guarded in any file: {sum('| guarded |' in r for r in rows)} of {len(rows)}.** The user's steps, "
        "replayed by code, show the bug on the old code and not on ours; our fix may differ from the upstream one, "
        "so read its diff before trusting it.", "",
        "| Upstream fix | Complaint | User | Result | Proof (evidence kinds) | Same file as real fix | Solved | Time |",
        "|---|---|---|---|---|---|---|---|", *rows, "",
        "## What each case needs (our reading of the misses, not a measurement)", "",
        *[f"- [#{c['pr']}](https://github.com/actualbudget/actual/pull/{c['pr']}): {c['note']}"
          for c in json.loads(CASES.read_text(encoding="utf-8"))["cases"] if c.get("note")], ""]), encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--report"]:  # combine results downloaded from parallel CI jobs, no app needed
        write_report(None)
    else:
        asyncio.run(main())
