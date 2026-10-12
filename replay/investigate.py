"""Investigate one complaint: reproduce on the live app, fix on a branch copy, then prove the fix.

Stages, in order: heard -> reproducing -> reproduced | not_reproduced | ux_confusion
                  -> fixing -> proving -> fixed | fix_unproven | fix_failed
"""

import shutil
import socket
from collections.abc import Callable
from pathlib import Path

from openai import AsyncOpenAI

from replay.agent import ReplayResult, replay
from replay.bugs import ROOT
from replay.conditions import Condition
from replay.fix import apply_patch, pick_fix_model, propose_fix
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
    """Proven = the same user no longer reproduces it, and the evidence kinds that proved the bug are gone."""
    proof_kinds = {e.kind for e in before.evidence if e.id in before.cited}
    return after.verdict != "reproduced" and not proof_kinds & {e.kind for e in after.evidence}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def investigate(case: dict, cond: Condition, live_url: str, source: Path,
                      client: AsyncOpenAI, chat: Chat, update: Update) -> dict:
    def stage(name: str) -> None:
        case["stage"] = name
        update(case)

    complaint = case["complaint"]
    policy, matcher = llm_policy(chat), llm_matcher(chat)

    stage("reproducing")
    before = await replay(live_url, complaint, cond, policy, matcher)
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
    patch = await propose_fix(client, fix_model, complaint, cond, before, branch)
    try:
        diff = apply_patch(patch, branch)
    except ValueError as e:
        case["fix"] = {"model": fix_model, "explanation": patch.explanation, "error": str(e)}
        stage("fix_failed")
        return case
    case["fix"] = {"model": fix_model, "explanation": patch.explanation, "diff": diff}

    stage("proving")
    with running_shop(branch, port=free_port()) as url:
        after = await replay(url, complaint, cond, policy, matcher)
    case["proof"] = as_dict(after)
    stage("fixed" if fix_proven(before, after) else "fix_unproven")
    return case
