"""The replay loop: observe -> policy picks one action -> act, until a verdict."""

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path

from replay.film import describe, write_gif
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
    heard: tuple[str, ...] = ()  # screen-reader users: what the last screen announces, in screen-reader words


# Roughly how screen readers name roles and states; structure with no words of its own is not spoken.
ROLE_WORDS = {"img": "image", "textbox": "edit", "combobox": "combo box", "checkbox": "check box",
              "radio": "radio button", "searchbox": "search edit", "spinbutton": "spin button"}
STATE_WORDS = {"disabled": "unavailable", "checked": "checked", "expanded": "expanded", "pressed": "pressed",
               "selected": "selected", "required": "required"}
VALUE_ROLES = {"textbox", "searchbox", "combobox", "spinbutton", "slider"}  # after the colon: a value, not a label
SILENT = {"list", "group", "generic", "none", "presentation", "rowgroup", "table", "row", "main", "navigation",
          "banner", "contentinfo", "region", "form", "article", "section"}
ARIA_LINE = re.compile(r'^(?P<role>[a-z]+)(?: "(?P<name>(?:[^"\\]|\\.)*)")?(?P<attrs>(?: \[[^\]]+\])*)'
                       r'(?::\s*(?P<val>.*))?$')


def spoken(aria: str, limit: int = 80) -> list[str]:
    """A Playwright aria snapshot as a screen reader would read it out: '1, button', 'image', 'Cart, heading level 2'."""
    said = []
    for raw in aria.splitlines():
        m = ARIA_LINE.match(raw.strip().removeprefix("- "))
        if not m:
            continue
        role, name, val = m["role"], m["name"] or "", (m["val"] or "").strip().strip('"')
        words = []
        for attr in re.findall(r"\[([^\]]+)\]", m["attrs"] or ""):
            key, _, level = attr.partition("=")
            words.append(f"level {level}" if key == "level" else STATE_WORDS.get(key, ""))
        if role in ("text", "paragraph", "listitem", "cell", "gridcell", "option") and not name:
            if val:
                said.append(val)
            continue
        if role in SILENT and not name:
            continue
        val = val if role in VALUE_ROLES else ""
        role_said = " ".join([ROLE_WORDS.get(role, role)] + [w for w in words if w.startswith("level")])
        said.append(", ".join(x for x in [name, role_said, *[w for w in words if w and not w.startswith("level")],
                                          val] if x))
    return said[:limit]


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
                 ready_text: str = "", film: Path | None = None) -> ReplayResult:
    """Replay a complaint. If `screenshot` is given, save what the user sees at the moment of the verdict.
    If `film` is given, save the whole replay there as a captioned GIF, ending on what was found.

    `hints` are facts about the app the twin may need (test accounts, test data), from the project config.
    `storage_state` is a saved login, so the twin starts signed in.
    """
    async with Session(base_url, condition, storage_state, checks, ready_text) as session:
        frames: list | None = [] if film else None
        await snap(session, frames, f"The user's screen: {condition.label}")
        result = await _drive(session, complaint, condition, policy, matcher, hints, frames)
        if screenshot:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            await session.page.screenshot(path=str(screenshot))
        if film:
            found = [e.detail for e in result.evidence if e.id in result.cited]
            await snap(session, frames, f"Found: {found[0]}" if found else f"Not reproduced. {result.summary[:140]}",
                       "alert" if found else "")
            write_gif(frames, film)
        if condition.screen_reader:
            try:
                result = replace(result, heard=tuple(spoken(await session.page.locator("body").aria_snapshot())))
            except Exception:  # a transcript is a nice-to-have, like a film frame
                pass
        return result


async def snap(session: Session, frames: list | None, caption: str, tone: str = "", idx: int | None = None) -> None:
    """One film frame: the screen as the user sees it, with a caption, and a box around control `idx` if given.
    No film, no screenshot."""
    if frames is None:
        return
    box = None
    try:
        size = session.page.viewport_size
        rect = await session.page.locator(f'[data-bc-idx="{idx}"]').first.bounding_box(timeout=1000)             if idx is not None and size else None
        if rect:
            box = (rect["x"] / size["width"], rect["y"] / size["height"],
                   rect["width"] / size["width"], rect["height"] / size["height"])
    except Exception:
        box = None
    try:
        frames.append((await session.page.screenshot(), caption, tone, box))
    except Exception:  # a frame is a nice-to-have; a page mid-navigation must not break the replay
        pass


async def _drive(session: Session, complaint: str, condition: Condition, policy: Policy,
                 matcher: Matcher | None, hints: str = "", frames: list | None = None) -> ReplayResult:
    steps: list[dict] = []
    visited: list[str] = []  # page paths in the order seen, so the twin can tell it is going in circles
    last_result = "(page just opened)"
    judged = 0
    prev_view = None
    seen: dict[int, str] = {}  # control number -> its name when last on screen
    refused = 0  # the twin's own "reproduced" claims the judge turned down
    # Keyboard users need many more presses than a tap to reach the same control (cloud case 8570 ran out of steps).
    budget = condition.max_steps * (2 if condition.keyboard_only else 1)
    for step in range(budget):
        obs = await session.observe()
        seen.update({e["idx"]: e["label"] for e in obs.get("elements", [])})
        if not visited or visited[-1] != obs["url"]:
            visited.append(obs["url"])
        view = page_signature(obs)
        if steps and view == prev_view and not last_result.startswith(("ok, it now", "ok, its mark", "ok, it is now")):
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
                if not match.get("evidence") and refused < CLAIM_RETRIES:
                    # Cloud case 8926 (run 14): a refused claim ended the replay after 3 of 25 steps.
                    refused += 1
                    last_result = ("not accepted: the browser recorded no evidence of this problem yet. Keep going "
                                   "the way the user did, to the screen where it happens")
                    continue
                action = ({"verdict": "reproduced", **match} if match.get("evidence") else
                          {"verdict": "not_reproduced",
                           "summary": str(action.get("summary", "")) + " [The judge found no evidence of this problem.]"})
            return judge(action, session.evidence, steps)
        label = next((e["label"] for e in obs.get("elements", []) if e["idx"] == action.get("target")), None)
        if action.get("type") in ("click", "fill") and label is None and action.get("target") in seen:
            # Cloud case 9107 (run 13): five taps on [32] from a menu that had closed, each a wasted step.
            here = [f"[{e['idx']}] {e['label']}" for e in obs.get("elements", [])][:12]
            last_result = (f"error: not tapped. [{action['target']}] was '{seen[action['target']]}' on an earlier screen; "
                           f"it is not on this one (a menu or dialog closed). Controls here now: {', '.join(here)}")
            continue
        taps =sum(1 for s in steps if s.get("target") == label and s["action"].get("type") == "click") if label else 0
        if action.get("type") == "click" and taps >= BLOCK_LIMIT:
            # Notes alone did not stop it: cloud case 9064 (run 9) reopened one scheduled payment eleven times.
            last_result = (f"error: not tapped. You already opened '{label}' {taps} times and it is not what you need; "
                           "choose a different control")
            continue
        # The frame is taken just before the step, with the control about to be used boxed: you see what it does.
        target = action.get("target") if action.get("type") in ("click", "fill") else None
        await snap(session, frames, f"Step {len(steps) + 1}: {describe(action, label)}",
                   idx=target if isinstance(target, int) else None)
        last_result = await session.act(action)
        steps.append({"action": action, "result": last_result, "target": session.last_target, "idx": session.last_idx})
        last_result += revisit_note(steps)
    await session.observe()
    if matcher and len(session.evidence) > judged:
        match = await matcher(complaint, list(session.evidence))
        if match.get("evidence"):
            return judge({"verdict": "reproduced", **match}, session.evidence, steps)
    stop = {"verdict": "not_reproduced", "summary": f"Stopped after {budget} steps."}
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
- If you finished the user's whole task and no matching evidence appeared, give "not_reproduced". Do not wander.
- A control marked (disabled) is not the bug by itself: apps disable fields while another one is being edited.
  Finish or close that first (press Enter, tap a neutral spot, or Escape), then try the control again."""

SIGHTED_ACTIONS = """{"type": "click", "target": <idx>}   (add "times": 2 to tap twice quickly, like an impatient user)
{"type": "fill", "target": <idx>, "text": "..."}
{"type": "press", "key": "Escape"}   (closes an open menu or dialog)"""
SCREEN_READER_ACTIONS = """{"type": "click_role", "role": "button", "name": "<exact accessible name>"}
{"type": "fill_role", "role": "textbox", "name": "<exact accessible name>", "text": "..."}
You can only use controls that have a name in the accessibility tree."""
KEYBOARD_ACTIONS = """{"type": "press", "key": "Tab" | "Shift+Tab" | "Enter" | "Space" | "Escape" | "ArrowDown" | "ArrowUp"}
   (add "times": 2-15 to press it several times, like holding Tab to move down the page)
{"type": "type", "text": "..."}   (types into the focused field)
This user has no mouse. "Focused" shows where the keyboard is now; press Tab to move to the next control."""


REVISIT_LIMIT = 3
CLAIM_RETRIES = 1  # after a refused "reproduced" claim, the twin keeps looking this many times before it stops
BLOCK_LIMIT = 5  # taps on one control before the twin is refused another


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
