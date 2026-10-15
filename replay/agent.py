"""The replay loop: observe -> policy picks one action -> act, until a verdict."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from replay.browser import Evidence, Session
from replay.conditions import Condition

VERDICTS = ("reproduced", "ux_confusion", "not_reproduced")
REPEAT_LIMIT = 3
Policy = Callable[[dict], Awaitable[dict]]


def page_signature(obs: dict) -> str:
    """What a user would notice changing: visible text, controls, and accessibility tree."""
    return json.dumps([obs["text"], [e["label"] for e in obs["elements"]], obs.get("aria", "")], ensure_ascii=False)


@dataclass(frozen=True)
class ReplayResult:
    verdict: str
    summary: str
    cited: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    steps: tuple[dict, ...]


def judge(action: dict, evidence: list[Evidence], steps: list[dict]) -> ReplayResult:
    """No evidence, no verdict: 'reproduced' must cite evidence the browser really collected."""
    known = {e.id for e in evidence}
    cited = tuple(i for i in action.get("evidence", []) if i in known)
    verdict = action.get("verdict") if action.get("verdict") in VERDICTS else "not_reproduced"
    summary = str(action.get("summary", ""))
    if verdict == "reproduced" and not cited:
        verdict, summary = "not_reproduced", summary + " [Downgraded: no machine evidence was cited.]"
    return ReplayResult(verdict, summary, cited, tuple(evidence), tuple(steps))


Matcher = Callable[[str, list[Evidence]], Awaitable[dict]]


async def replay(base_url: str, complaint: str, condition: Condition, policy: Policy,
                 matcher: Matcher | None = None, screenshot: Path | None = None, hints: str = "",
                 storage_state: Path | None = None) -> ReplayResult:
    """Replay a complaint. If `screenshot` is given, save what the user sees at the moment of the verdict.

    `hints` are facts about the app the twin may need (test accounts, test data), from the project config.
    `storage_state` is a saved login, so the twin starts signed in.
    """
    async with Session(base_url, condition, storage_state) as session:
        result = await _drive(session, complaint, condition, policy, matcher, hints)
        if screenshot:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            await session.page.screenshot(path=str(screenshot))
        return result


async def _drive(session: Session, complaint: str, condition: Condition, policy: Policy,
                 matcher: Matcher | None, hints: str = "") -> ReplayResult:
    steps: list[dict] = []
    last_result = "(page just opened)"
    judged = 0
    prev_view = None
    for step in range(condition.max_steps):
        obs = await session.observe()
        view = page_signature(obs)
        if steps and view == prev_view:
            last_result += " (nothing visible changed)"
        recent = {json.dumps({k: v for k, v in s["action"].items() if k != "why"}, sort_keys=True)
                  for s in steps[-REPEAT_LIMIT:]}
        if len(steps) >= REPEAT_LIMIT and len(recent) == 1:
            last_result += f" (you did the same action {REPEAT_LIMIT} times in a row; try something else)"
        prev_view = view
        if matcher and len(session.evidence) > judged:
            judged = len(session.evidence)
            match = await matcher(complaint, list(session.evidence))
            if match.get("evidence"):
                return judge({"verdict": "reproduced", **match}, session.evidence, steps)
        action = await policy({
            "complaint": complaint, "condition": condition, "obs": obs, "step": step,
            "evidence": list(session.evidence), "steps": steps, "last_result": last_result, "hints": hints,
        })
        if action.get("type") == "verdict":
            return judge(action, session.evidence, steps)
        last_result = await session.act(action)
        steps.append({"action": action, "result": last_result, "target": session.last_target, "idx": session.last_idx})
    await session.observe()
    if matcher and len(session.evidence) > judged:
        match = await matcher(complaint, list(session.evidence))
        if match.get("evidence"):
            return judge({"verdict": "reproduced", **match}, session.evidence, steps)
    stop = {"verdict": "not_reproduced", "summary": f"Stopped after {condition.max_steps} steps."}
    return judge(stop, session.evidence, steps)


def scripted_policy(actions: list[dict]) -> Policy:
    """Replays fixed actions, then stops. Used by tests to check bugs without a model."""
    queue = list(actions)

    async def policy(_: dict) -> dict:
        return queue.pop(0) if queue else {"type": "verdict", "verdict": "not_reproduced", "summary": "script done"}

    return policy


SYSTEM_PROMPT = """You check whether a user's complaint about a website is real by replaying it in a real browser.
The browser already runs under the user's real conditions (network, phone, language, assistive tech).
Act like that user: try to do what they were trying to do. When a form needs data, use what "About this app" gives.
If the complaint says what the user did (typed a wrong OTP, used a coupon code, opened the cart), do exactly that.
Finish the whole flow the complaint is about: if it is about paying or being charged, actually press pay.
If the complaint lists what the user did just before, repeat those steps in the same order (for example: type the
coupon, then press Apply, then Pay) before any verdict. Skipping one of them can hide the bug.

Reply with ONE JSON object and nothing else: {"thought": "<one short sentence>", "action": {...}}
Actions:
{ACTIONS}
{"type": "goto", "path": "/<path on the same site>"}   (only if the complaint names a page you cannot reach by clicking)
{"type": "wait", "ms": <up to 10000>}
{"type": "scroll", "direction": "down" | "up"}
{"type": "verdict", "verdict": "reproduced" | "ux_confusion" | "not_reproduced", "evidence": ["E1", ...], "summary": "<2 sentences>"}

Rules:
- "reproduced" MUST cite evidence ids from the Evidence list that match the complaint. Never invent evidence.
- "ux_confusion": nothing is technically broken, but this user would get lost. Explain where.
- "not_reproduced": you repeated every step the user took and finished their task without hitting the problem.
- The moment the Evidence list has an item that matches the complaint, give the "reproduced" verdict citing it.
- If you finished the user's whole task and no matching evidence appeared, give "not_reproduced". Do not wander."""

SIGHTED_ACTIONS = """{"type": "click", "target": <idx>}   (add "times": 2 to tap twice quickly, like an impatient user)
{"type": "fill", "target": <idx>, "text": "..."}"""
SCREEN_READER_ACTIONS = """{"type": "click_role", "role": "button", "name": "<exact accessible name>"}
{"type": "fill_role", "role": "textbox", "name": "<exact accessible name>", "text": "..."}
You can only use controls that have a name in the accessibility tree."""
KEYBOARD_ACTIONS = """{"type": "press", "key": "Tab" | "Shift+Tab" | "Enter" | "Space" | "Escape" | "ArrowDown" | "ArrowUp"}
{"type": "type", "text": "..."}   (types into the focused field)
This user has no mouse. "Focused" shows where the keyboard is now; press Tab to move to the next control."""


def build_prompt(ctx: dict) -> tuple[str, str]:
    cond: Condition = ctx["condition"]
    actions = (KEYBOARD_ACTIONS if cond.keyboard_only else SCREEN_READER_ACTIONS if cond.screen_reader
               else SIGHTED_ACTIONS)
    obs = ctx["obs"]
    page = (
        f"Accessibility tree (what the screen reader announces):\n{obs['aria']}"
        if cond.screen_reader
        else "Controls you can see:\n" + "\n".join(
            f"[{e['idx']}] {e['tag']} '{e['label']}'" + (f" value='{e['value']}'" if e["value"] else "")
            for e in obs["elements"]
        ) + f"\n\nVisible text:\n{obs['text']}"
    )
    if cond.keyboard_only:
        focus = obs.get("focus")
        page = (f"Focused: {focus['tag']} '{focus['label']}'" if focus else "Focused: nothing yet") + \
            f"\n\nVisible text:\n{obs['text']}"
    about = f"About this app: {ctx['hints']}\n" if ctx.get("hints") else ""
    evidence = "\n".join(f"{e.id} [{e.kind}] {e.detail}" for e in ctx["evidence"]) or "(none yet)"
    history = "\n".join(json.dumps(s["action"]) + " -> " + s["result"] for s in ctx["steps"][-6:]) or "(none)"
    user = (
        f"Complaint: {ctx['complaint']}\nUser: {cond.persona}\n{about}"
        f"Step {ctx['step'] + 1} of {cond.max_steps}. Last action result: {ctx['last_result']}\n\n"
        f"Recent actions:\n{history}\n\n{page}\n\nEvidence collected by the browser:\n{evidence}"
    )
    return SYSTEM_PROMPT.replace("{ACTIONS}", actions), user
