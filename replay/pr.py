"""Turn a proven fix into a GitHub pull request: the patch, the guard test, screenshots and the evidence.

Works in a separate git worktree, so the developer's own checkout (and any uncommitted work) is never touched.
Commits are made as "Complaint Replay", never as the person running it. Needs `git` and `gh` (logged in, or
GH_TOKEN set, as in GitHub Actions).
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from replay.fix import Patch, apply_patch

BOT = {"GIT_AUTHOR_NAME": "Complaint Replay", "GIT_AUTHOR_EMAIL": "complaint-replay@users.noreply.github.com",
       "GIT_COMMITTER_NAME": "Complaint Replay", "GIT_COMMITTER_EMAIL": "complaint-replay@users.noreply.github.com"}
SHOTS = ".complaint-replay/shots"
TITLE_MAX = 72
GITHUB_REMOTE = re.compile(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$")


def run(args: list[str], cwd: Path) -> str:
    out = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", env={**os.environ, **BOT})
    if out.returncode:
        raise RuntimeError(f"{' '.join(args[:3])} failed: {(out.stderr or out.stdout).strip()[:400]}")
    return out.stdout.strip()


def origin_slug(repo: Path) -> str:
    """owner/name of the repo's own `origin`. Never ask gh to guess: with an `upstream` remote (a fork),
    gh picks the upstream project, and the pull request would land in someone else's repo."""
    url = run(["git", "remote", "get-url", "origin"], repo)
    match = GITHUB_REMOTE.search(url)
    if not match:
        raise RuntimeError(f"origin is not a GitHub repo: {url}")
    return match.group(1)


def title(case: dict) -> str:
    said = " ".join((case.get("said") or case["complaint"]).split())
    text = f"fix: \"{said}\""  # the user's own words say what broke better than any label
    return text if len(text) <= TITLE_MAX else text[:TITLE_MAX - 2] + "…\""


def body(case: dict, image_url: str = "") -> str:
    """What a reviewer needs in 30 seconds: who hit it, the proof, the fix, how it is guarded."""
    rep, fix, guard = case["replay"], case["fix"], case.get("guard", {})
    cited = [e for e in rep["evidence"] if e["id"] in rep["cited"]]
    reports = f" ({case['reports']} reports)" if case.get("reports", 1) > 1 else ""
    lines = [
        f"> {case.get('said') or case['complaint']}",
        "",
        f"**Who hit it:** {case['condition']['persona']}{reports}",
        "",
        "### Proof (collected by the browser, not written by a model)",
        *[f"- `{e['kind']}` {e['detail']}" for e in cited],
        "",
        "### Steps that triggered it",
        *[f"{i + 1}. {s['action'].get('type')} " + (f"`{s['target']}`" if s.get("target") else "")
          for i, s in enumerate(rep["steps"])],
        "",
        "### The fix",
        fix.get("explanation", ""),
    ]
    if fix.get("sources"):
        lines += ["", "Sources: " + ", ".join(f"[{s['title']}]({s['url']})" for s in fix["sources"])]
    shots = case.get("shots") or {}
    if image_url and shots:
        cells = [f"![{k}]({image_url}/{shots[k]}?raw=true)" for k in ("before", "after") if k in shots]
        lines += ["", "| Before | After |", "|---|---|", "| " + " | ".join(cells) + " |"]
    lines += [
        "",
        "### Guard test",
        f"`{guard.get('file', '')}` replays the same user and steps. Passes on this branch: "
        f"**{'yes' if guard.get('passes_on_fix') else 'no'}**. Fails on the old code: "
        f"**{'yes' if guard.get('catches_bug') else 'no'}**. Run it with `crp guard`.",
        "",
        f"<sub>Found, fixed and proven by [Complaint Replay](https://github.com/yashasviyadav30/complaint-replay) "
        f"with {fix.get('model', 'NVIDIA Nemotron')}. Review it like any other PR.</sub>",
    ]
    return "\n".join(lines)


def open_pr(repo: Path, case: dict, shots: Path | None = None, base: str = "", push: bool = True) -> str:
    """Create branch complaint-replay/<case id> with the fix, guard and screenshots; open the PR. Returns its URL."""
    repo = Path(run(["git", "rev-parse", "--show-toplevel"], repo))
    branch = f"complaint-replay/{case['id']}"
    base = base or run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    work = Path(tempfile.mkdtemp(prefix="crp-pr-"))
    work.rmdir()  # git worktree add wants to create it
    run(["git", "worktree", "add", "-B", branch, str(work), "HEAD"], repo)
    try:
        apply_patch(Patch(case["fix"]["explanation"], tuple(case["fix"]["edits"])), work)
        guard = case["guard"]
        (work / guard["file"]).parent.mkdir(parents=True, exist_ok=True)
        (work / guard["file"]).write_text(json.dumps(guard["test"], ensure_ascii=False, indent=2), encoding="utf-8")
        for name in (case.get("shots") or {}).values():
            if shots and (shots / name).exists():
                (work / SHOTS).mkdir(parents=True, exist_ok=True)
                shutil.copy(shots / name, work / SHOTS / name)
        run(["git", "add", "-A"], work)
        run(["git", "commit", "-m", title(case), "-m", case["fix"]["explanation"]], work)
        if not push:
            return branch
        slug = origin_slug(repo)
        run(["git", "push", "--force", "-u", "origin", branch], work)
        body_file = Path(tempfile.gettempdir()) / f"crp-{case['id']}-pr.md"
        body_file.write_text(body(case, f"https://github.com/{slug}/blob/{branch}/{SHOTS}"), encoding="utf-8")
        try:
            return run(["gh", "pr", "create", "--repo", slug, "--base", base, "--head", branch, "--title", title(case),
                        "--body-file", str(body_file)], work).splitlines()[-1]
        except RuntimeError as e:
            if "not permitted to create" in str(e):
                raise RuntimeError("GitHub Actions may not open pull requests in this repo yet. Turn on Settings > "
                                   "Actions > General > 'Allow GitHub Actions to create and approve pull requests' "
                                   f"(the fix is already pushed to branch {branch}).") from e
            if "already exists" not in str(e):
                raise
            return run(["gh", "pr", "view", branch, "--repo", slug, "--json", "url", "-q", ".url"], work)
    finally:
        run(["git", "worktree", "remove", "--force", str(work)], repo)
