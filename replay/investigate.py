"""Investigate one complaint: reproduce on the live app, fix on a branch copy, then prove the fix.

Stages, in order: heard -> reproducing -> reproduced | not_reproduced | ux_confusion
                  -> fixing -> proving -> fixed | fix_unproven | fix_failed -> guarded
"""

import json
import shutil
from collections.abc import Callable
from pathlib import Path

from openai import AsyncOpenAI

from replay.agent import ReplayResult, replay
from replay.bugs import ROOT
from replay.conditions import Condition
from replay.fix import apply_patch, pick_fix_model, propose_fix
from replay.guard import build_guard, run_guard
from replay.research import research
from replay.llm import Chat, llm_matcher, llm_policy
from replay.shop import running_shop

BRANCHES = ROOT / "workspace" / "branches"
Update = Callable[[dict], None]


def as_dict(r: ReplayResult) -> dict:
    return {
        "verdict": r.verdict, "summary": r.summary, "cited": list(r.cited),
        "evidence": [{"id": e.id, "kind": e.kind, "detail": e.detail, "step": e.step} for e in r.evidence],
        "steps": list(r.steps),
    }


def fix_proven(before: ReplayResult, after: ReplayResult) -> bool:
    """Proven = replaying the same user on the fixed code, the evidence that proved the bug never appears.

    The proof run's own verdict is not used: in testing, the twin once typed a wrong OTP during the proof,
    got an unrelated HTTP 400, and a loose verdict blocked a correct fix. Unrelated evidence stays visible
    in the case for a human to read, it just does not decide.
    """
    proof_kinds = {e.kind for e in before.evidence if e.id in before.cited}
    return bool(proof_kinds) and not proof_kinds & {e.kind for e in after.evidence}


async def investigate(case: dict, cond: Condition, live_url: str, source: Path,
                      client: AsyncOpenAI, chat: Chat, update: Update, shots: Path | None = None) -> dict:
    def stage(name: str) -> None:
        case["stage"] = name
        update(case)

    complaint = case["complaint"]
    policy, matcher = llm_policy(chat), llm_matcher(chat)

    def shot(name: str) -> Path | None:
        if not shots:
            return None
        case.setdefault("shots", {})[name] = f"{case['id']}-{name}.png"
        return shots / case["shots"][name]

    stage("reproducing")
    before = await replay(live_url, complaint, cond, policy, matcher, shot("before"))
    case["replay"] = as_dict(before)
    if before.verdict != "reproduced":
        stage(before.verdict)
        return case
    stage("reproduced")

    branch = BRANCHES / case["id"]
    shutil.rmtree(branch, ignore_errors=True)
    shutil.copytree(source, branch, ignore=shutil.ignore_patterns("__pycache__"))
    stage("fixing")
    fix_model = await pick_fix_model(client)
    sources = await research([e for e in before.evidence if e.id in before.cited])
    patch = await propose_fix(client, fix_model, complaint, cond, before, branch, sources)
    try:
        diff = apply_patch(patch, branch)
    except ValueError as e:
        case["fix"] = {"model": fix_model, "explanation": patch.explanation, "error": str(e)}
        stage("fix_failed")
        return case
    case["fix"] = {"model": fix_model, "explanation": patch.explanation, "diff": diff,
                   "sources": [{"title": s["title"], "url": s["url"]} for s in sources]}

    stage("proving")
    with running_shop(branch) as url:
        after = await replay(url, complaint, cond, policy, matcher, shot("after"))
    case["proof"] = as_dict(after)
    if not fix_proven(before, after):
        stage("fix_unproven")
        return case
    stage("fixed")

    # Guard: the proof replay becomes a test. It must pass on the fix AND fail on the old code,
    # otherwise it would not actually catch the bug coming back.
    kinds = {e.kind for e in before.evidence if e.id in before.cited}
    guard = build_guard(case["id"], complaint, cond, list(after.steps), kinds)
    guard_file = branch / "guards" / f"{case['id']}.json"
    guard_file.parent.mkdir(exist_ok=True)
    guard_file.write_text(json.dumps(guard, ensure_ascii=False, indent=2), encoding="utf-8")
    with running_shop(branch) as url:
        on_fix = await run_guard(url, guard)
    on_bug = await run_guard(live_url, guard)
    case["guard"] = {"file": f"guards/{case['id']}.json", "steps": len(guard["steps"]),
                     "passes_on_fix": on_fix["passed"], "catches_bug": not on_bug["passed"]}
    if on_fix["passed"] and not on_bug["passed"]:
        stage("guarded")
    else:
        update(case)
    return case
