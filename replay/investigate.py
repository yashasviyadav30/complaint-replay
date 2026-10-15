"""Investigate one complaint: reproduce on the live app, fix on a branch copy, then prove the fix.

Stages, in order: heard -> reproducing -> reproduced | not_reproduced | ux_confusion
                  -> fixing -> proving -> fixed | fix_unproven | fix_failed -> guarded
"""

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from openai import AsyncOpenAI

from replay.agent import ReplayResult, replay
from replay.browser import evidence_key
from replay.conditions import Condition, with_needs
from replay.fix import apply_patch, pick_fix_model, propose_fix
from replay.guard import build_guard, run_guard
from replay.research import research
from replay.llm import Chat, llm_matcher, llm_policy, stated_needs
from replay.project import load_project, running_app

BRANCHES = Path(tempfile.gettempdir()) / "complaint-replay" / "branches"
# Installed dependencies are linked into the branch copy, not copied (node_modules can be gigabytes).
LINKED = {"node_modules", ".venv", "venv"}
GUARDS = ".complaint-replay/guards"
FIX_ATTEMPTS = 2
Update = Callable[[dict], None]


def as_dict(r: ReplayResult) -> dict:
    return {
        "verdict": r.verdict, "summary": r.summary, "cited": list(r.cited),
        "evidence": [{"id": e.id, "kind": e.kind, "detail": e.detail, "step": e.step} for e in r.evidence],
        "steps": list(r.steps),
    }


def proof_keys(result: ReplayResult) -> set[str]:
    """The exact problems that proved the bug (one bad button, not every button of that kind)."""
    return {evidence_key(e.kind, e.detail) for e in result.evidence if e.id in result.cited}


def _link(src: Path, dst: Path) -> None:
    if os.name == "nt":
        import _winapi  # a directory junction needs no admin rights, unlike a symlink
        _winapi.CreateJunction(str(src), str(dst))
    else:
        os.symlink(src, dst, target_is_directory=True)


def remove_branch(branch: Path) -> None:
    for name in LINKED:
        link = branch / name
        if link.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(link)):
            os.unlink(link) if link.is_symlink() else os.rmdir(link)  # remove the link, never what it points to
    shutil.rmtree(branch, ignore_errors=True)


def branch_copy(source: Path, branch: Path, deps: Path | None = None) -> Path:
    """A working copy of the app to fix, the way a pull request branch would hold it.

    Installed dependencies are linked from `deps` (default: the source itself).
    """
    remove_branch(branch)
    shutil.copytree(source, branch, ignore=shutil.ignore_patterns("__pycache__", ".git", *LINKED))
    for name in LINKED:
        if ((deps or source) / name).is_dir():
            _link(((deps or source) / name).resolve(), branch / name)
    return branch


async def investigate(case: dict, cond: Condition, live_url: str, source: Path,
                      client: AsyncOpenAI, chat: Chat, update: Update, shots: Path | None = None) -> dict:
    def stage(name: str) -> None:
        case["stage"] = name
        update(case)

    complaint = case["complaint"]
    policy, matcher = llm_policy(chat), llm_matcher(chat)
    project = load_project(source)
    target = {"hints": project.hints, "storage_state": project.auth_file}

    def shot(name: str) -> Path | None:
        if not shots:
            return None
        case.setdefault("shots", {})[name] = f"{case['id']}-{name}.png"
        return shots / case["shots"][name]

    if cond.key == "twin":  # measured by the widget: add what the user said about themselves
        cond = with_needs(cond, await stated_needs(chat, case.get("said") or complaint))
        case["condition"] = {"label": cond.label, "persona": cond.persona}

    stage("reproducing")
    before = await replay(live_url, complaint, cond, policy, matcher, shot("before"), **target)
    case["replay"] = as_dict(before)
    if before.verdict != "reproduced":
        stage(before.verdict)
        return case
    stage("reproduced")

    branch = branch_copy(source, BRANCHES / case["id"])
    stage("fixing")
    fix_model = await pick_fix_model(client)
    sources = await research([e for e in before.evidence if e.id in before.cited])
    rejected = None
    for _ in range(FIX_ATTEMPTS):  # a rejected (ambiguous or unsafe) edit gets one retry with the reason
        patch = await propose_fix(client, fix_model, complaint, cond, before, branch, sources, rejected, project.edit)
        try:
            diff = apply_patch(patch, branch, project.edit)
            break
        except ValueError as e:
            rejected = str(e)
    else:
        case["fix"] = {"model": fix_model, "explanation": patch.explanation, "error": rejected}
        stage("fix_failed")
        return case
    case["fix"] = {"model": fix_model, "explanation": patch.explanation, "diff": diff, "edits": list(patch.edits),
                   "sources": [{"title": s["title"], "url": s["url"]} for s in sources]}

    # Proof and guard are one thing: the exact steps that triggered the bug, replayed by code, no model.
    # A fresh model-driven proof replay once "proved" a fix by never reaching the broken screen at all.
    stage("proving")
    guard = build_guard(case["id"], complaint, cond, list(before.steps), proof_keys(before))
    guard_file = branch / GUARDS / f"{case['id']}.json"
    guard_file.parent.mkdir(parents=True, exist_ok=True)
    guard_file.write_text(json.dumps(guard, ensure_ascii=False, indent=2), encoding="utf-8")
    with running_app(branch) as url:
        on_fix = await run_guard(url, guard, project.auth_file, shot("after"))
    on_bug = await run_guard(live_url, guard, project.auth_file)
    case["proof"] = {"passed": on_fix["passed"], "evidence": on_fix["evidence"], "steps": len(guard["steps"])}
    case["guard"] = {"file": f"{GUARDS}/{case['id']}.json", "steps": len(guard["steps"]), "test": guard,
                     "passes_on_fix": on_fix["passed"], "catches_bug": not on_bug["passed"]}
    if not on_fix["passed"]:
        stage("fix_unproven")
        return case
    stage("guarded" if case["guard"]["catches_bug"] else "fixed")
    return case
