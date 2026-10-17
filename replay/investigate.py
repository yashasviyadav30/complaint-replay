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
FIX_ATTEMPTS = 3  # the third catches a malformed reply after a rejected edit (cloud case 9064)
PROOF_ROUNDS = 2  # a patch the proof rejects gets one more try, told what the proof still saw
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


def dependency_dirs(root: Path) -> list[Path]:
    """Every installed-dependency folder, at any depth (monorepos keep one per package), relative to root."""
    found = []
    for here, dirs, _ in os.walk(root):
        for name in list(dirs):
            if name in LINKED:
                found.append((Path(here) / name).relative_to(root))
            if name in LINKED or name == ".git":
                dirs.remove(name)  # never walk into them
    return found


def is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(path))


def remove_branch(branch: Path) -> None:
    if branch.exists():
        for rel in dependency_dirs(branch):
            if is_link(branch / rel):
                (branch / rel).unlink() if (branch / rel).is_symlink() else os.rmdir(branch / rel)  # the link only
    shutil.rmtree(branch, ignore_errors=True)


def branch_copy(source: Path, branch: Path, deps: Path | None = None) -> Path:
    """A working copy of the app to fix, the way a pull request branch would hold it.

    Installed dependencies (at any depth) are linked from `deps` (default: the source itself), not copied.
    """
    remove_branch(branch)
    shutil.copytree(source, branch, ignore=shutil.ignore_patterns("__pycache__", ".git", *LINKED))
    deps = deps or source
    for rel in dependency_dirs(deps):
        if (branch / rel).parent.is_dir() and not (branch / rel).exists():
            _link((deps / rel).resolve(), branch / rel)
    return branch


async def investigate(case: dict, cond: Condition, live_url: str, source: Path,
                      client: AsyncOpenAI, chat: Chat, update: Update, shots: Path | None = None) -> dict:
    def stage(name: str) -> None:
        case["stage"] = name
        update(case)

    complaint = case["complaint"]
    policy, matcher = llm_policy(chat), llm_matcher(chat)
    project = load_project(source)
    target = {"hints": project.hints, "storage_state": project.auth_file, "checks": project.check_scripts,
              "ready_text": project.ready_text}

    def shot(name: str) -> Path | None:
        if not shots:
            return None
        case.setdefault("shots", {})[name] = f"{case['id']}-{name}.png"
        return shots / case["shots"][name]

    if not (cond.screen_reader or cond.keyboard_only):  # add what the user said about themselves
        cond = with_needs(cond, await stated_needs(chat, case.get("said") or complaint))
        case["condition"] = {"label": cond.label, "persona": cond.persona}

    stage("reproducing")
    before = await replay(live_url, complaint, cond, policy, matcher, shot("before"), **target)
    case["replay"] = as_dict(before)
    if before.verdict != "reproduced":
        stage(before.verdict)
        return case
    # The guard exists as soon as the bug is proven: if the fix fails, it is the acceptance test for whoever
    # (person or coding agent) takes the task over.
    guard = build_guard(case["id"], complaint, cond, list(before.steps), proof_keys(before))
    case["guard"] = {"file": f"{GUARDS}/{case['id']}.json", "steps": len(guard["steps"]), "test": guard}
    stage("reproduced")

    branch = branch_copy(source, BRANCHES / case["id"])
    stage("fixing")
    fix_model = await pick_fix_model(client)
    sources = await research([e for e in before.evidence if e.id in before.cited])
    still_broken = None  # set when a patch applied but the replayed steps still showed the bug
    tried: tuple[str, ...] = ()
    for proof_round in range(PROOF_ROUNDS):
        if proof_round:
            branch = branch_copy(source, BRANCHES / case["id"])  # a fresh copy: the failed patch is gone
            stage("fixing")
        rejected, patch, errors = still_broken, None, []  # every attempt's reason: the first often says more
        for _ in range(FIX_ATTEMPTS):  # a rejected edit, or an unreadable reply, gets a retry with the reason
            try:
                tried = tuple(str(e.get("file", "")) for e in patch.edits) if patch else tried
                patch = await propose_fix(client, fix_model, complaint, cond, before, branch, sources, rejected,
                                          project.edit, tried)
                diff = apply_patch(patch, branch, project.edit)
                break
            except ValueError as e:  # includes a reply that was not valid JSON (seen on a big real repo)
                rejected = str(e)[:300]
                errors.append(rejected)
        else:
            case["fix"] = {"model": fix_model, "explanation": patch.explanation if patch else "", "error": rejected,
                           "errors": errors, "edits": list(patch.edits) if patch else []}  # what it tried
            stage("fix_failed")
            return case
        case["fix"] = {"model": fix_model, "explanation": patch.explanation, "diff": diff, "edits": list(patch.edits),
                       "sources": [{"title": s["title"], "url": s["url"]} for s in sources]}

        # Proof and guard are one thing: the exact steps that triggered the bug, replayed by code, no model.
        # A fresh model-driven proof replay once "proved" a fix by never reaching the broken screen at all.
        stage("proving")
        guard_file = branch / GUARDS / f"{case['id']}.json"
        guard_file.parent.mkdir(parents=True, exist_ok=True)
        guard_file.write_text(json.dumps(guard, ensure_ascii=False, indent=2), encoding="utf-8")
        with running_app(branch) as url:
            on_fix = await run_guard(url, guard, project.auth_file, shot("after"), project.check_scripts,
                                     project.ready_text)
        if on_fix["passed"]:
            break
        # One more round with what the proof saw. Cloud case 8733 (run 8) named the right function
        # (deserializeTransaction) but patched its caller; the guard said no, and the fixer never heard why.
        tried = tuple(str(e.get("file", "")) for e in patch.edits)
        still_broken = ("your patch applied, but replaying the user's steps on it still shows the bug: "
                        + json.dumps(on_fix["evidence"], ensure_ascii=False)[:300]
                        + ". Look again for the real cause, maybe in a function the code you changed calls")
    on_bug = await run_guard(live_url, guard, project.auth_file, checks=project.check_scripts,
                             ready_text=project.ready_text)
    case["proof"] = {"passed": on_fix["passed"], "evidence": on_fix["evidence"], "steps": len(guard["steps"])}
    case["guard"] = {"file": f"{GUARDS}/{case['id']}.json", "steps": len(guard["steps"]), "test": guard,
                     "passes_on_fix": on_fix["passed"], "catches_bug": not on_bug["passed"]}
    if not on_fix["passed"]:
        stage("fix_unproven")
        return case
    stage("guarded" if case["guard"]["catches_bug"] else "fixed")
    return case
