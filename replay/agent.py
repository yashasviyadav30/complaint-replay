"""The replay loop: observe -> policy picks one action -> act, until a verdict."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from replay.browser import Evidence, Session
from replay.conditions import Condition

VERDICTS = ("reproduced", "ux_confusion", "not_reproduced")
REPEAT_LIMIT = 3
STUCK_LIMIT = 6  # the same action this many times: the twin is lost, stop instead of burning tokens
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
                 storage_state: Path | None = None, checks: dict[str, str] | None = None,
                 ready_text: str = "") -> ReplayResult:
    """Replay a complaint. If `screenshot` is given, save what the user sees at the moment of the verdict.

    `hints` are facts about the app the twin may need (test accounts, test data), from the project config.
    `storage_state` is a saved login, so the twin starts signed in.
    """
    async with Session(base_url, condition, storage_state, checks, ready_text) as session:
        result = await _drive(session, complaint, condition, policy, matcher, hints)
        if screenshot:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            await session.page.screenshot(path=str(screenshot))
        return result


async def _drive(session: Session, complaint: str, condition: Condition, policy: Policy,
                 matcher: Matcher | None, hints: str = "") -> ReplayResult:
    steps: list[dict] = []
    visited: list[str] = []  # page paths in the order seen, so the twin can tell it is going in circles
    last_result = "(page just opened)"
    judged = 0
    prev_view = None
    for step in range(condition.max_steps):
        obs = await session.observe()
        if not visited or visited[-1] != obs["url"]:
            visited.append(obs["url"])
        view = page_signature(obs)
        if steps and view == prev_view:
            last_result += " (nothing visible changed)"
        recent = {json.dumps({k: v for k, v in s["action"].items() if k != "why"}, sort_keys=True)
                  for s in steps[-REPEAT_LIMIT:]}
        last_few = {json.dumps({k: v for k, v in s["action"].items() if k != "why"}, sort_keys=True)
                    for s in steps[-STUCK_LIMIT:]}
        # Tab, Tab, Tab is how keyboard users move, and waiting for a slow app is what a patient user does.
        moving = bool(steps) and steps[-1]["action"].get("type") in ("press", "wait")
        if len(steps) >= STUCK_LIMIT and len(last_few) == 1 and not moving:
            stop = {"verdict": "not_reproduced", "summary": f"Stuck: the same action {STUCK_LIMIT} times in a row."}
            return judge(stop, session.evidence, steps)
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
            "evidence": list(session.evidence), "steps": steps, "last_result": last_result, "hints": hints, "visited": visited,
        })
        if action.get("type") == "verdict":
            if action.get("verdict") == "reproduced" and matcher:
                # The twin's own claim goes through the same checks as the judge's (speed filter, skeptic question):
                # it cited "page loaded slowly" for a payee bug, skipping them (cloud case 8926, run 8).
                match = await matcher(complaint, list(session.evidence))
                action = ({"verdict": "reproduced", **match} if match.get("evidence") else
                          {"verdict": "not_reproduced",
                           "summary": str(action.get("summary", "")) + " [The judge found no evidence of this problem.]"})
            return judge(action, session.evidence, steps)
        last_result = await session.act(action)
        steps.append({"action": action, "result": last_result, "target": session.last_target, "idx": session.last_idx})
        last_result += revisit_note(steps)
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
   (add "times": 2-15 to press it several times, like holding Tab to move down the page)
{"type": "type", "text": "..."}   (types into the focused field)
This user has no mouse. "Focused" shows where the keyboard is now; press Tab to move to the next control."""


REVISIT_LIMIT = 3


def revisit_note(steps: list[dict]) -> str:
    """A loop the stuck rule can't see (open X, Close, open X, Close): name the control tapped again and again.
    Cloud case 9064 (run 8) reopened one scheduled payment eight times looking for a transaction's edit screen."""
    target = steps[-1].get("target") if steps[-1]["action"].get("type") == "click" else None
    if not target:
        return ""
    n = sum(1 for s in steps if s.get("target") == target and s["action"].get("type") == "click")
    if n < REVISIT_LIMIT:
        return ""
    return f" (you have tapped '{target}' {n} times already; it does not lead where you want: try a different control)"


EVIDENCE_PER_KIND = 3


def evidence_brief(evidence: list) -> str:
    """Evidence for the twin, at most a few items per kind: 25 'slow request' lines from a cold page load made it
    believe the app was still loading (cloud case 8733). The judge still sees every item."""
    shown, extra = [], {}
    for e in evidence:
        if sum(1 for s in shown if s.kind == e.kind) < EVIDENCE_PER_KIND:
            shown.append(e)
        else:
            extra[e.kind] = extra.get(e.kind, 0) + 1
    lines = [f"{e.id} [{e.kind}] {e.detail}" for e in shown] + [f"(+{n} more {k})" for k, n in extra.items()]
    return "\n".join(lines) or "(none yet)"


def build_prompt(ctx: dict) -> tuple[str, str]:
    cond: Condition = ctx["condition"]
    actions = (KEYBOARD_ACTIONS if cond.keyboard_only else SCREEN_READER_ACTIONS if cond.screen_reader
               else SIGHTED_ACTIONS)
    obs = ctx["obs"]
    page = (
        f"Accessibility tree (what the screen reader announces):\n{obs['aria']}"
        if cond.screen_reader
        else "Controls you can see:\n" + "\n".join(
            f"[{e['idx']}] {e['tag']} '{e['label']}'" + (f" value='{e['value']}'" if e["value"] else "") +
            (" (new)" if e.get("new") else "") + (" (disabled)" if e.get("disabled") else "")
            for e in obs["elements"]
        ) + f"\n\nVisible text:\n{obs['text']}"
    )
    if cond.keyboard_only:
        focus = obs.get("focus")
        # A keyboard-only user still sees the screen: show the controls, which they reach only with keys.
        page = (f"Focused: {focus['tag']} '{focus['label']}'" if focus else "Focused: nothing yet") + \
            "\n\nControls you can see (in page order, roughly the Tab order; reach them only with keys):\n" + \
            "\n".join(f"- {e['tag']} '{e['label']}'" for e in obs["elements"]) + f"\n\nVisible text:\n{obs['text']}"
    about = f"About this app: {ctx['hints']}\n" if ctx.get("hints") else ""
    evidence = evidence_brief(ctx["evidence"])
    # The name of what each action hit: with bare numbers, a twin "opening a transaction" pressed
    # 'Previous month' nine times without noticing (cloud case 9064).
    history = "\n".join(json.dumps({k: v for k, v in s["action"].items() if k != "why"}, ensure_ascii=False) +
                        (f" on '{s['target']}'" if s.get("target") else "") + " -> " + s["result"]
                        for s in ctx["steps"][-6:]) or "(none)"
    user = (
        f"Complaint: {ctx['complaint']}\nUser: {cond.persona}\n{about}"
        f"Step {ctx['step'] + 1} of {cond.max_steps}. Last action result: {ctx['last_result']}\n"
        f"Pages visited so far, in order: {' > '.join(ctx.get('visited', [])[-10:]) or '(this is the first)'}\n\n"
        f"Recent actions:\n{history}\n\n{page}\n\nEvidence collected by the browser:\n{evidence}"
    )
    return SYSTEM_PROMPT.replace("{ACTIONS}", actions), user
