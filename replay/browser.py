"""A real browser under a user's real conditions, plus machine-collected evidence.

Evidence is only ever added by code watching the browser, never by the model.
That is the "no evidence, no verdict" rule.
"""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from replay.conditions import Condition

AXE_JS = Path(__file__).resolve().parent.parent / "vendor" / "axe.min.js"
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
MONEY_KEYS = ("total", "charged", "amount")
SETTLE_TIMEOUT_S = 20
OUR_PATHS = ("/widget.js", "/api/complaints")


def is_ours(url: str) -> bool:
    return urlparse(url).path in OUR_PATHS

OBSERVE_JS = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const visible = (el) => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0
      && (el.offsetParent !== null || s.position === 'fixed');
  };
  // aria-label plus visible text, so a sighted user's view of badges/counts ("Cart 3") is kept
  const name = (el) => {
    const parts = [el.getAttribute('aria-label'), el.innerText || el.value || el.placeholder || el.title
      || (el.labels && el.labels[0] && el.labels[0].innerText)].map((s) => (s || '').trim()).filter(Boolean);
    return [...new Set(parts)].join(' ').replace(/\s+/g, ' ').slice(0, 60);
  };
  document.querySelectorAll('[data-bc-idx]').forEach((el) => el.removeAttribute('data-bc-idx'));
  const elements = [], offscreen = [];
  let i = 0;
  for (const el of document.querySelectorAll('button, a[href], input, select, textarea, [role=button]')) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.left >= vw || r.right <= 0) { offscreen.push({ label: name(el), left: Math.round(r.left), vw }); continue; }
    el.setAttribute('data-bc-idx', i);
    elements.push({ idx: i++, tag: el.tagName.toLowerCase(), label: name(el), value: el.value || '' });
  }
  const alerts = [...document.querySelectorAll('[role=alert], [aria-live]')]
    .filter(visible).map((e) => e.innerText.trim()).filter(Boolean);
  return { url: location.pathname, vw, elements, offscreen, alerts, text: document.body.innerText.slice(0, 1200) };
}
"""

AXE_RUN_JS = """
async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } }))
  .violations.map((v) => ({ id: v.id, help: v.help, targets: v.nodes.slice(0, 3).map((n) => n.target.join(' ')) }))
"""


@dataclass(frozen=True)
class Evidence:
    id: str
    kind: str
    detail: str
    step: int


class Session:
    """Async context manager: one browser page under one condition."""

    def __init__(self, base_url: str, condition: Condition):
        self.base_url = base_url
        self.condition = condition
        self.evidence: list[Evidence] = []
        self.step = 0
        self._seen: set[tuple[str, str]] = set()
        self._inflight = 0
        self._amounts: list[tuple[str, str, float]] = []

    def add(self, kind: str, detail: str) -> None:
        if (kind, detail) in self._seen:
            return
        self._seen.add((kind, detail))
        self.evidence.append(Evidence(f"E{len(self.evidence) + 1}", kind, detail, self.step))

    async def __aenter__(self) -> "Session":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch()
        context = await self._browser.new_context(**self.condition.context)
        if self.condition.zoom != 1.0:
            await context.add_init_script(
                f"addEventListener('DOMContentLoaded', () => document.documentElement.style.zoom = '{self.condition.zoom}')"
            )
        await context.route("**/*", self._route)
        self.page = await context.new_page()
        self._listen()
        if self.condition.cpu_slowdown > 1:
            cdp = await context.new_cdp_session(self.page)
            await cdp.send("Emulation.setCPUThrottlingRate", {"rate": self.condition.cpu_slowdown})
        await self.page.goto(self.base_url, wait_until="load", timeout=60_000)
        return self

    async def __aexit__(self, *exc) -> None:
        await self._browser.close()
        await self._pw.stop()

    async def _route(self, route) -> None:
        if is_ours(route.request.url):  # the twin must never file complaints about itself
            await route.fulfill(status=204, body="")
            return
        if self.condition.network:
            # CDP network throttling was silently ignored in tests (Playwright 1.63), so latency is
            # added per request here. ponytail: latency only; add bandwidth limits if a bug needs them.
            await asyncio.sleep(self.condition.network["latency"] / 1000)
        await route.continue_()

    def _listen(self) -> None:
        page = self.page
        page.on("request", lambda r: self._track(+1))
        page.on("requestfinished", lambda r: self._track(-1))
        page.on("requestfailed", self._on_failed)
        page.on("response", self._on_response)
        page.on("console", lambda m: m.type == "error" and self.add("console_error", m.text[:200]))
        page.on("pageerror", lambda e: self.add("console_error", str(e)[:200]))

    def _track(self, delta: int) -> None:
        self._inflight = max(0, self._inflight + delta)

    def _on_failed(self, request) -> None:
        self._track(-1)
        if is_ours(request.url):
            return
        self.add("request_failed", f"{request.method} {urlparse(request.url).path} failed ({request.failure})")

    async def _on_response(self, response) -> None:
        if is_ours(response.url):
            return
        path = urlparse(response.url).path
        if response.status >= 400:
            self.add("http_error", f"{response.request.method} {path} returned HTTP {response.status}")
        if not path.startswith("/api/") or "json" not in response.headers.get("content-type", ""):
            return
        try:
            body = await response.json()
        except Exception:  # body can vanish if the page navigates; nothing to compare then
            return
        if isinstance(body, dict):
            for key in MONEY_KEYS:
                if isinstance(body.get(key), (int, float)):
                    self._record_amount(path, key, body[key])

    def _record_amount(self, path: str, key: str, value: float) -> None:
        # ponytail: compares only the last two money values from different endpoints;
        # a per-flow money ledger is the upgrade if real apps need it.
        if self._amounts and self._amounts[-1][0] != path and self._amounts[-1][2] != value:
            prev_path, prev_key, prev_value = self._amounts[-1]
            self.add("amount_mismatch", f"{prev_path} said {prev_key}={prev_value} but {path} said {key}={value}")
        self._amounts.append((path, key, value))

    async def settle(self) -> None:
        """Wait until network requests finish, like a user waiting for the screen."""
        for _ in range(SETTLE_TIMEOUT_S * 10):
            await asyncio.sleep(0.1)
            if self._inflight == 0:
                break
        await asyncio.sleep(0.3)

    async def observe(self) -> dict:
        obs = await self.page.evaluate(OBSERVE_JS)
        for o in obs["offscreen"]:
            self.add("offscreen_control", f"'{o['label']}' is outside the screen (left={o['left']}px, screen={o['vw']}px)")
        if self.condition.hindi:
            for alert in obs["alerts"]:
                if not DEVANAGARI.search(alert):
                    self.add("language_mismatch", f"Hindi user was shown an English-only message: '{alert}'")
        if self.condition.screen_reader:
            obs["aria"] = await self.page.locator("body").aria_snapshot()
            for v in await self._axe():
                self.add("a11y_violation", f"{v['id']}: {v['help']} ({', '.join(v['targets'])})")
        return obs

    async def _axe(self) -> list[dict]:
        if not await self.page.evaluate("typeof axe !== 'undefined'"):
            await self.page.add_script_tag(path=str(AXE_JS))
        return await self.page.evaluate(AXE_RUN_JS)

    async def act(self, action: dict) -> str:
        """Run one action. Returns 'ok' or a short error the model can react to."""
        self.step += 1
        page, kind = self.page, action.get("type")
        try:
            if kind == "click":
                await page.locator(f'[data-bc-idx="{int(action["target"])}"]').click(timeout=5000)
            elif kind == "fill":
                await page.locator(f'[data-bc-idx="{int(action["target"])}"]').fill(str(action["text"]), timeout=5000)
            elif kind in ("click_role", "fill_role"):
                if not action.get("name"):
                    return "error: a screen reader cannot use a control without a name"
                target = page.get_by_role(action["role"], name=action["name"]).first
                if kind == "click_role":
                    await target.click(timeout=5000)
                else:
                    await target.fill(str(action["text"]), timeout=5000)
            elif kind == "click_css":  # scripted tests only
                await page.locator(action["selector"]).first.click(timeout=5000)
            elif kind == "fill_css":  # scripted tests only
                await page.locator(action["selector"]).first.fill(str(action["text"]), timeout=5000)
            elif kind in ("scroll", "swipe"):
                await page.mouse.wheel(0, -600 if action.get("direction") == "up" else 600)
            elif kind == "wait":
                await asyncio.sleep(min(int(action.get("ms", 1000)), 10_000) / 1000)
            else:
                return f"error: unknown action type {kind!r}"
        except Exception as e:  # report to the model; a failed click is information, not a crash
            return f"error: {str(e).splitlines()[0][:200]}"
        await self.settle()
        return "ok"
