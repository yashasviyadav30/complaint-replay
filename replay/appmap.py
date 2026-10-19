"""App map: explore an app's navigation once, so the twin can go straight to any screen.

Big apps made the twin wander: on Actual Budget it ticked boxes on the budget page and never opened an account
(cloud case 8765). The map lists screens, each with the clicks that reach it from the first screen. Only
navigation is explored (links, tabs, menu items, sidebars; on a screen with none, its buttons), never anything that
sounds like it changes data.
"""

import re
import time
from pathlib import Path

from replay.browser import Session
from replay.conditions import Condition

MAX_SCREENS = 30
MAX_DEPTH = 3
MAX_SECONDS = 360  # a big app gets a partial map rather than a long wait
DANGER = re.compile(r"delete|remove|log ?out|sign ?out|reset|clear|close account|unsubscribe|\bpay|buy|order|checkout|"
                    r"submit|send|save|confirm|discard|archive|import|export|download|print|cancel", re.I)
TITLE_JS = r"""() => {
  const d = [...document.querySelectorAll('[role=dialog], dialog[open]')].filter((e) => e.getBoundingClientRect().width > 0).pop();
  const h = (d || document).querySelector('h1, h2, [role=heading]');
  return ((h && h.innerText) || (d && d.innerText) || document.title || location.pathname).trim().replace(/\s+/g, ' ').slice(0, 80);
}"""


async def follow(session: Session, path: list[str]) -> list[dict] | None:
    """From the first screen, tap each control in `path` by its visible name. The steps taken, or None if lost."""
    await session.restart()
    steps = [{"action": {"type": "goto", "path": ""}, "result": "ok", "target": None, "idx": None}]
    for label in path:
        obs = await session.observe()
        idx = next((e["idx"] for e in obs["elements"] if e["label"] == label), None)
        if idx is None:
            return None
        result = await session.act({"type": "click", "target": idx})
        if result.startswith("error"):
            return None
        steps.append({"action": {"type": "click", "target": idx, "why": "app map"}, "result": result,
                      "target": session.last_target, "idx": session.last_idx})
    return steps


def leads_on(elements: list[dict], path: list[str]) -> list[str]:
    """Labels worth exploring from here: navigation, or on a screen without any (a welcome page), its buttons."""
    nav = [e for e in elements if e.get("nav")] or elements
    return [e["label"] for e in nav if e["label"] and not e.get("disabled") and not DANGER.search(e["label"])
            and e["label"] not in path and not e["label"].startswith("(no name")]


async def build_map(base_url: str, condition: Condition, storage_state: Path | None = None,
                    ready_text: str = "") -> list[dict]:
    """Breadth first from the first screen; each screen keeps the shortest path that reaches it."""
    started, screens, seen, queue = time.monotonic(), [], set(), [[]]
    async with Session(base_url, condition, storage_state, None, ready_text) as session:  # its evidence is discarded
        while queue and len(screens) < MAX_SCREENS and time.monotonic() - started < MAX_SECONDS:
            path = queue.pop(0)
            if await follow(session, path) is None:
                continue
            obs = await session.observe()
            title = await session.page.evaluate(TITLE_JS)
            if (obs["url"], title) in seen:
                continue
            seen.add((obs["url"], title))
            labels = [e["label"] for e in obs["elements"] if e["label"]]
            screens.append({"id": len(screens), "title": title, "url": obs["url"], "path": path,
                            "controls": labels[:15]})
            if len(path) < MAX_DEPTH:
                queue += [path + [label] for label in dict.fromkeys(leads_on(obs["elements"], path))]
    return screens


def describe(screens: list[dict]) -> str:
    """The map as the twin reads it."""
    return "\n".join(f"S{s['id']}: {s['title']} (via: {' > '.join(s['path']) or 'first screen'}; "
                     f"controls: {', '.join(s['controls'][:8])})" for s in screens)
