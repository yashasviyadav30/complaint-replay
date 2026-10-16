"""Benchmark on real bugs: re-create each one by reverse-applying its real upstream fix, then run the whole chain.

Usage: uv run python scripts/bench_real.py <path to the app's git checkout> [pr ...]
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
CASE_TIMEOUT_S = 25 * 60
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
    rep = case.get("replay") or {}
    cited = [e["kind"] for e in rep.get("evidence", []) if e["id"] in rep.get("cited", [])]
    return (f"| [#{spec['pr']}](https://github.com/actualbudget/actual/pull/{spec['pr']}) | {spec['complaint'][:70]}… | "
            f"{case['condition']['label']} | {stage} | {', '.join(cited) or '-'} | {same} | {seconds / 60:.0f} min |")


async def main() -> None:
    load_dotenv(ROOT / ".env")
    repo = Path(sys.argv[1]).resolve()
    wanted = {int(a) for a in sys.argv[2:]}
    specs = [s for s in json.loads(CASES.read_text(encoding="utf-8"))["cases"] if not wanted or s["pr"] in wanted]
    client = make_client()
    chat = Chat(client, await pick_model(client))
    rows = []
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
        rows.append(row(spec, case, files, time.monotonic() - started))
    REPORT.write_text("\n".join([
        "# Real bugs: Actual Budget", "",
        f"Measured {time.strftime('%Y-%m-%d')} with `uv run python scripts/bench_real.py <actual checkout>`, model "
        f"`{chat.model}`. Each bug was fixed upstream; it is re-created by reverse-applying that fix to today's code, "
        "and the complaint is written from the real report. \"Same file\" means our fix edited a file the real fix "
        "edited. Every case is listed, misses included.", "",
        "| Upstream fix | Complaint | User | Result | Proof (evidence kinds) | Same file as real fix | Time |",
        "|---|---|---|---|---|---|---|", *rows, ""]), encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    asyncio.run(main())
