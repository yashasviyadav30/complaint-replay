"""crp: Complaint Replay from the command line and from CI.

    crp replay "Pay button is missing on my phone" --device "Galaxy S9+" --network 3g      reproduce only
    crp replay "..." --fix --pr                     reproduce, fix, prove, guard, open a pull request
    crp replay --payload case.json --fix --pr       a complaint sent by the service (GitHub Action)
    crp guard                                       run every guard test against the app (CI)
    crp auth --url https://staging.example.com      log in once by hand; the twin reuses the session
    crp devices pixel                               list device profiles
    crp init                                        add complaint-replay.toml and the GitHub workflow
    crp mcp                                         serve replays and guards to coding agents (MCP, stdio)

Run inside the app's repo. Model keys come from the environment or a .env file:
NEBIUS_API_KEY (Nebius Token Factory) or NVIDIA_API_KEY (build.nvidia.com).
"""

import argparse
import asyncio
import json
import sys
import urllib.request
import uuid
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from replay.conditions import CONDITIONS, NETWORKS, devices, profile, twin_condition
from replay.project import CONFIG, load_project, running_app

RUNS = ".complaint-replay/runs"
GUARDS = ".complaint-replay/guards"
WORKFLOW = Path(__file__).with_name("workflow.yml")
CONFIG_TEMPLATE = """[app]
# How to start the app from the repo root. {port} is filled in with a free port.
start = "__START__"
ready = "/"
# Or replay an already running site (staging, preview) instead of starting one:
# url = "https://staging.example.com"
# Test data the twin may use in forms (never real customer data):
hints = ""
# Saved login from `crp auth` (keep it out of git):
# auth = ".complaint-replay/auth.json"
# Files the fixer may change (empty = any source file):
edit = []
# Your own checks, run on every page the twin sees: each file holds `() => [ "problem", ... ]`.
# Example: checks = ["checks/invoice_total.js"]
checks = []
# Text that shows once the app is usable, if it loads slowly (the twin waits for it, up to 3 minutes):
ready_text = ""
"""
DONE = {"guarded", "fixed", "reproduced", "not_reproduced", "ux_confusion"}


def condition_from(args: argparse.Namespace, payload: dict | None):
    if payload:  # measured by the widget, plus what the project's sector pack asks for
        return replace(twin_condition(payload["env"]), audit=bool((payload.get("pack") or {}).get("audit")))
    if args.user:
        return CONDITIONS[args.user]
    return profile(args.device, args.network, args.locale, args.timezone, "dark" if args.dark else "",
                   args.reduced_motion, args.forced_colors, args.zoom, args.screen_reader, args.keyboard,
                   args.steps)


def new_case(complaint: str, cond, payload: dict | None) -> dict:
    payload = payload or {}
    return {"id": payload.get("case_id") or uuid.uuid4().hex[:12], "created_at": datetime.now(timezone.utc).isoformat(),
            "kind": payload.get("kind", "spoken"), "complaint": complaint, "said": payload.get("said") or complaint,
            "reports": payload.get("reports", 1), "condition": {"label": cond.label, "persona": cond.persona},
            "stage": "heard"}


def report(payload: dict | None, case: dict) -> None:
    """Send progress back to the service that sent this complaint, if one did."""
    if not payload or not payload.get("callback"):
        return
    req = urllib.request.Request(payload["callback"], json.dumps(case, ensure_ascii=False).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {payload.get('token', '')}"})
    try:
        urllib.request.urlopen(req, timeout=15)
    except OSError as e:  # the replay must finish even if the service is asleep or down
        print(f"  (could not update the service: {e})", file=sys.stderr)


def target(repo: Path, url: str | None):
    """The app to replay: a URL the user gave (nothing to start), or the repo's app started on a free port."""
    return nullcontext(url.rstrip("/")) if url else running_app(repo)


async def cmd_replay(args: argparse.Namespace) -> int:
    from replay.agent import replay
    from replay.investigate import as_dict, investigate
    from replay.llm import Chat, llm_matcher, llm_policy, make_client, pick_model

    repo = Path(args.repo).resolve()
    payload = json.loads(Path(args.payload).read_text(encoding="utf-8")) if args.payload else None
    complaint = args.complaint or (payload or {}).get("complaint", "")
    if not complaint:
        print("error: say what the user complained about, or pass --payload", file=sys.stderr)
        return 2
    cond = condition_from(args, payload)
    case = new_case(complaint, cond, payload)
    out = repo / RUNS
    out.mkdir(parents=True, exist_ok=True)

    def save(c: dict) -> None:
        (out / f"{c['id']}.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [{c['stage']}]", flush=True)
        report(payload, c)

    client = make_client()
    chat = Chat(client, await pick_model(client))
    project = load_project(repo)
    print(f"Replaying as: {cond.persona}\nComplaint: {complaint}", flush=True)
    with target(repo, args.url) as url:
        if args.fix:
            keep_shots = (payload or {}).get("pack", {}).get("screenshots", True)
            case = await investigate(case, cond, url, repo, client, chat, save, out / "shots" if keep_shots else None)
        else:
            shot, film = f"{case['id']}-before.png", f"{case['id']}-before.gif"
            from replay.appmap import build_map

            app_map = [] if cond.keyboard_only else await build_map(url, cond, project.auth_file, project.ready_text)
            result = await replay(url, complaint, cond, llm_policy(chat), llm_matcher(chat), out / "shots" / shot,
                                  hints=project.hints, storage_state=project.auth_file, checks=project.check_scripts,
                                  ready_text=project.ready_text, film=out / "shots" / film, app_map=app_map)
            case.update(replay=as_dict(result), stage=result.verdict, shots={"before": shot}, films={"before": film})
            save(case)
    show(case)
    if args.pr and case["stage"] == "guarded":
        from replay.pr import open_pr

        case["pr"] = open_pr(repo, case, out / "shots", args.base)
        save(case)
        print(f"Pull request: {case['pr']}")
    elif args.pr and case["stage"] in ("fix_failed", "fix_unproven") and case.get("guard"):
        from replay.pr import open_issue

        from replay.pr import issue_body, title
        from replay.trackers import file_everywhere

        case["issue"] = open_issue(repo, case)  # the bug is proven; hand the fix to a person or a coding agent
        case["tracker_links"] = file_everywhere(title(case).replace("fix:", "bug:", 1), issue_body(case))
        save(case)
        print(f"Issue for a person or coding agent: {case['issue']}", *case["tracker_links"])
    if args.issue:
        from replay.pr import comment_on_issue

        comment_on_issue(repo, args.issue, case)
    return 0 if case["stage"] in DONE else 1


def show(case: dict) -> None:
    rep = case.get("replay", {})
    print(f"\nVerdict: {case['stage']}\n{rep.get('summary', '')}")
    for e in rep.get("evidence", []):
        mark = "*" if e["id"] in rep.get("cited", []) else " "
        print(f" {mark} {e['id']} [{e['kind']}] {e['detail']}")
    if "fix" in case:
        print(f"\nFix: {case['fix'].get('explanation') or case['fix'].get('error')}\n{case['fix'].get('diff', '')}")
    if "guard" in case:
        g = case["guard"]
        print(f"Guard {g['file']}: passes on fix={g['passes_on_fix']}, fails on old code={g['catches_bug']}")


async def cmd_guard(args: argparse.Namespace) -> int:
    from replay.guard import run_all

    repo = Path(args.repo).resolve()
    guards = sorted((repo / GUARDS).glob("*.json"))
    if not guards:
        print(f"No guard tests in {GUARDS}. Nothing to check.")
        return 0
    with target(repo, args.url) as url:
        results = await run_all(url, guards, load_project(repo).auth_file, load_project(repo).check_scripts,
                                    load_project(repo).ready_text)
    failed = [k for k, v in results.items() if not v["passed"]]
    for name, r in results.items():
        print(("PASS " if r["passed"] else "FAIL ") + name + "".join(f"\n     {e['kind']}: {e['detail']}" for e in r["evidence"]))
    print(f"\n{len(results) - len(failed)}/{len(results)} guards pass")
    if args.base and not failed:
        return await guards_catch_bug_on_base(repo, args.base, guards)
    return 1 if failed else 0


async def guards_catch_bug_on_base(repo: Path, base: str, guards: list[Path]) -> int:
    """For guards this branch adds: they must FAIL on the base branch, or they don't test the bug at all."""
    import shutil
    import tempfile

    from replay.guard import run_all
    from replay.investigate import branch_copy, remove_branch
    from replay.pr import run

    existing = set(run(["git", "ls-tree", "-r", "--name-only", base, "--", GUARDS], repo).splitlines())
    new = [g for g in guards if f"{GUARDS}/{g.name}" not in existing]
    if not new:
        print(f"No new guards compared with {base}.")
        return 0
    work = Path(tempfile.mkdtemp(prefix="crp-base-"))
    work.rmdir()
    run(["git", "worktree", "add", "--detach", str(work), base], repo)
    old = branch_copy(work, Path(tempfile.mkdtemp(prefix="crp-old-")) / "app", deps=repo)  # base has no deps installed
    try:
        with running_app(old) as url:
            results = await run_all(url, new, load_project(repo).auth_file, load_project(repo).check_scripts,
                                    load_project(repo).ready_text)
    finally:
        remove_branch(old)
        run(["git", "worktree", "remove", "--force", str(work)], repo)
        shutil.rmtree(work, ignore_errors=True)
    missed = [k for k, v in results.items() if v["passed"]]
    for name, r in results.items():
        print(f"{'catches the bug on ' + base if not r['passed'] else 'DOES NOT catch the bug on ' + base}: {name}")
    return 1 if missed else 0


async def cmd_auth(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    out = Path(args.repo).resolve() / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        await (await context.new_page()).goto(args.url)
        await asyncio.to_thread(input, "Log in with a TEST account in the browser window, then press Enter here... ")
        await context.storage_state(path=str(out))
        await browser.close()
    print(f"Saved the login to {out}. Add `auth = \"{args.out}\"` to {CONFIG}, and keep the file out of git.")
    return 0


def cmd_devices(args: argparse.Namespace) -> int:
    for name, d in devices().items():
        if not args.filter or args.filter.lower() in name.lower():
            vp = d["viewport"]
            print(f"{name:40} {vp['width']}x{vp['height']}  {'touch' if d.get('has_touch') else ''}")
    print("\nNetworks: " + ", ".join(NETWORKS) + "\nReady-made users (--user): " + ", ".join(CONDITIONS))
    return 0


def cmd_setup(_: argparse.Namespace) -> int:
    """Download the browsers the twin drives, Chrome's and Safari's engines (and, on Linux CI, their libraries)."""
    import subprocess

    extra = ["--with-deps"] if sys.platform == "linux" else []
    return subprocess.call([sys.executable, "-m", "playwright", "install", *extra, "chromium", "webkit"])


def guess_start(repo: Path) -> str:
    """The start command `init` writes: the package's dev script with its package manager, else a static server."""
    try:
        scripts = json.loads((repo / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
    except (OSError, ValueError):
        return "{python} -m http.server {port} --bind 127.0.0.1"  # no package.json: serve the files as they are
    script = "dev" if "dev" in scripts or "start" not in scripts else "start"
    if (repo / "pnpm-lock.yaml").exists():
        return f"pnpm {script} --port {{port}}"
    if (repo / "yarn.lock").exists():
        return f"yarn {script} --port {{port}}"
    return f"npm run {script} -- --port {{port}}"


def cmd_init(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    written = []
    if not (repo / CONFIG).exists():
        (repo / CONFIG).write_text(CONFIG_TEMPLATE.replace("__START__", guess_start(repo)), encoding="utf-8")
        written.append(CONFIG)
    wf = repo / ".github" / "workflows" / "complaint-replay.yml"
    if not wf.exists():
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text(WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(wf.relative_to(repo).as_posix())
    ignore = repo / ".gitignore"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.exists() else []
    lines += [e for e in (".complaint-replay/runs/", ".complaint-replay/auth.json") if e not in lines]
    ignore.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote: " + (", ".join(written) or "nothing new") + ".\nNext: check `start` in " + CONFIG +
          ", add NEBIUS_API_KEY as a repository secret, and commit.")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay", help="replay a complaint as the user who made it")
    r.add_argument("complaint", nargs="?", default="")
    r.add_argument("--repo", default=".")
    r.add_argument("--url", help="replay this running site instead of starting the app")
    r.add_argument("--payload", help="JSON from the Complaint Replay service (widget conditions included)")
    r.add_argument("--user", choices=sorted(CONDITIONS), help="a ready-made user, e.g. hindi, elderly, keyboard")
    r.add_argument("--device", default="", help="a device profile name, see `crp devices`")
    r.add_argument("--network", default="wifi", choices=list(NETWORKS))
    r.add_argument("--locale", default="")
    r.add_argument("--timezone", default="")
    r.add_argument("--dark", action="store_true")
    r.add_argument("--reduced-motion", action="store_true")
    r.add_argument("--forced-colors", action="store_true")
    r.add_argument("--zoom", type=float, default=1.0)
    r.add_argument("--keyboard", action="store_true", help="no mouse: Tab, Enter, Space only")
    r.add_argument("--screen-reader", action="store_true")
    r.add_argument("--steps", type=int, default=20, help="how many actions the twin may take")
    r.add_argument("--fix", action="store_true", help="also fix, prove and guard (needs the source)")
    r.add_argument("--pr", action="store_true", help="open a pull request when the fix is guarded")
    r.add_argument("--base", default="", help="branch the pull request targets (default: current)")
    r.add_argument("--issue", type=int, help="post the result as a comment on this GitHub issue")
    g = sub.add_parser("guard", help="run every guard test (for CI)")
    g.add_argument("--repo", default=".")
    g.add_argument("--url")
    g.add_argument("--base", default="", help="also check that guards new on this branch fail on this ref")
    a = sub.add_parser("auth", help="save a test login for the twin")
    a.add_argument("--url", required=True)
    a.add_argument("--repo", default=".")
    a.add_argument("--out", default=".complaint-replay/auth.json")
    d = sub.add_parser("devices", help="list device profiles")
    d.add_argument("filter", nargs="?", default="")
    sub.add_parser("setup", help="install the browser the twin uses")
    i = sub.add_parser("init", help="add the config file and GitHub workflow to a repo")
    i.add_argument("--repo", default=".")
    m = sub.add_parser("mcp", help="serve replays and guards to coding agents over MCP (stdio)")
    m.add_argument("--repo", default=".")
    return p


def main(argv: list[str] | None = None) -> None:
    load_dotenv(Path.cwd() / ".env")
    sys.stdout.reconfigure(encoding="utf-8")  # complaints and pages can be in any script
    args = parser().parse_args(argv)
    handlers = {"replay": cmd_replay, "guard": cmd_guard, "auth": cmd_auth}
    if args.cmd in handlers:
        sys.exit(asyncio.run(handlers[args.cmd](args)))
    if args.cmd == "mcp":
        from replay.mcp_server import serve  # optional: pip install "complaint-replay[mcp]"

        return serve(args.repo)
    sys.exit({"devices": cmd_devices, "init": cmd_init, "setup": cmd_setup}[args.cmd](args))


if __name__ == "__main__":
    main()
