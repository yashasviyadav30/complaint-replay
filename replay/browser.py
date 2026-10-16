"""A real browser under a user's real conditions, plus machine-collected evidence.

Evidence is only ever added by code watching the browser, never by the model.
That is the "no evidence, no verdict" rule.
"""

import asyncio
import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from replay.conditions import Condition
from replay.langid import base, detect, not_in

HERE = Path(__file__).resolve().parent
AXE_JS = HERE / "axe.min.js"
OBSERVE_JS = (HERE / "observe.js").read_text(encoding="utf-8")
MONEY_KEYS = ("total", "charged", "amount", "grand_total", "amount_due")
SETTLE_TIMEOUT_S = 20
# ponytail: payment-like paths by name; a per-app list of non-idempotent endpoints is the upgrade.
PAYMENT_PATH = re.compile(r"checkout|order|pay|purchase|transfer|booking", re.I)
DUPLICATE_WINDOW_S = 5
DOUBLE_TAP_GAP_MS = 300
OUR_PATHS = ("/widget.js", "/api/complaints")
SLOW_REQUEST_S = 10        # a request the user waited on this long
STUCK_LOADING_S = 15       # a spinner still on screen after this long
REDIRECT_LOOP = (4, 10.0)  # same URL loaded this many times within this many seconds
POOR_LCP_MS, POOR_CLS = 4000, 0.25  # web.dev "poor" thresholds
KEYS = {"Tab", "Shift+Tab", "Enter", "Space", "Escape", "ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight",
        "Home", "End", "PageDown", "PageUp"}

VITALS_JS = """
window.__crp = { lcp: 0, cls: 0 };
try {
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__crp.lcp = Math.max(window.__crp.lcp, e.startTime); })
    .observe({ type: 'largest-contentful-paint', buffered: true });
  new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__crp.cls += e.value; })
    .observe({ type: 'layout-shift', buffered: true });
} catch (e) {}
"""
# What kind of element a control is, in the words its source code uses (<input type="date" ...>): the fixer
# searches the code for these, since a visible label like '2026-10-16' appears in no source file.
ELEMENT_JS = """
(el) => {
  const attrs = ['type', 'name', 'id', 'role', 'data-testid'].filter(a => el.getAttribute(a))
    .map(a => `${a}="${el.getAttribute(a).slice(0, 40)}"`);
  return `<${el.tagName.toLowerCase()}${attrs.length ? ' ' + attrs.join(' ') : ''}>`;
}
"""
# The option a keyboard user sees highlighted in a dropdown, and the field it belongs to (for wrong_option_chosen).
HIGHLIGHTED_JS = """
() => {
  const a = document.activeElement;
  if (!a) return null;
  const id = a.getAttribute('aria-activedescendant');
  let opt = id ? document.getElementById(id) : null;
  if (!opt) opt = document.querySelector('[role=listbox] [role=option][aria-selected=true]');
  if (!opt) return null;
  a.setAttribute('data-crp-field', '1');
  return { option: (opt.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 60), field: true };
}
"""
CHOSEN_JS = """
() => {
  const f = document.querySelector('[data-crp-field]');
  if (!f) return null;
  f.removeAttribute('data-crp-field');
  return ('value' in f && f.value !== undefined) ? String(f.value) : (f.innerText || '');
}
"""
READY_TIMEOUT_S = 20
READY_TEXT_TIMEOUT_S = 180
BUSY_JS = """() => [...document.querySelectorAll('[aria-busy=true], [role=progressbar], [class*=spinner], [class*=loading]')]
  .some((e) => e.getBoundingClientRect().width > 0)"""
# Playwright's click error names what took the tap: "- <div class=...> intercepts pointer events".
INTERCEPTS = re.compile(r"(<[^>]{1,200}>)[^\n]*intercepts pointer events")
# Everything a tap could change that a user (or assistive tech) would notice. Same before and after = dead control.
FINGERPRINT_JS = """
() => {
  const states = [...document.querySelectorAll('[aria-expanded],[aria-pressed],[aria-checked],[aria-selected],details,dialog')]
    .map((e) => [e.getAttribute('aria-expanded'), e.getAttribute('aria-pressed'), e.getAttribute('aria-checked'),
                 e.getAttribute('aria-selected'), e.open].join(',')).join('|');
  const fields = [...document.querySelectorAll('input,select,textarea')]
    .map((e) => (e.type === 'checkbox' || e.type === 'radio') ? e.checked : e.value).join('|');
  // Focus is left out on purpose: tapping any button focuses it, which says nothing about whether it worked.
  return [location.href, document.querySelectorAll('*').length, document.body.innerText, states, fields].join('\\u0001');
}
"""
AXE_RUN_JS = """
async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } }))
  .violations.map((v) => ({ id: v.id, help: v.help, targets: v.nodes.slice(0, 3).map((n) => n.target.join(' ')) }))
"""


NUMBER = re.compile(r"\d+(?:\.\d+)?")


def evidence_key(kind: str, detail: str) -> str:
    """The same problem seen again, even if pixel sizes or timings differ: numbers are blanked out.

    ponytail: a fix that renames the broken control changes its key; compare by control position if that bites.
    """
    return f"{kind}: {NUMBER.sub('#', detail)}"


def at(item: dict) -> str:
    """ (in the navigation, near 'Book')" for evidence details, or nothing."""
    return f" ({item['where']})" if item.get("where") else ""


def is_ours(url: str) -> bool:
    return urlparse(url).path in OUR_PATHS


async def tap(locator, action: dict) -> None:
    """Click once, or twice in quick succession ("times": 2) the way an impatient user taps."""
    for i in range(min(int(action.get("times", 1)), 2)):
        if i:
            await asyncio.sleep(DOUBLE_TAP_GAP_MS / 1000)
        await locator.click(timeout=5000)


@dataclass(frozen=True)
class Evidence:
    id: str
    kind: str
    detail: str
    step: int


class Session:
    """Async context manager: one browser page under one condition."""

    def __init__(self, base_url: str, condition: Condition, storage_state: Path | None = None,
                 checks: dict[str, str] | None = None, ready_text: str = ""):
        self.base_url = base_url
        self.condition = condition
        self.storage_state = storage_state
        self.checks = checks or {}  # the project's own evidence checks: {name: JS returning a list of problems}
        self.ready_text = ready_text
        self.evidence: list[Evidence] = []
        self.step = 0
        self._seen: set[tuple[str, str]] = set()
        self._inflight = 0
        self._requests = 0  # every request the page sent, for "tapped, nothing happened"
        self._typed: list[tuple[object, str, str]] = []  # (element handle, field name, what the user typed)
        self._amounts: list[tuple[str, str, float]] = []
        self._labels: dict[int, str] = {}  # idx -> visible name, from the latest observe()
        self.last_target: str | None = None  # name of the control the last action used
        self.last_idx: int | None = None  # and its position among the page's controls
        self._opened: str | None = None  # control whose last tap changed the screen (it may have opened a menu)
        self._payments: list[tuple[float, str, str]] = []  # (time, path, body) of payment-like POSTs
        self._started: dict[object, float] = {}  # request -> start time
        self._navigations: deque[tuple[float, str]] = deque(maxlen=20)
        self._busy_since: dict[str, float] = {}
        self._loaded = False  # flaky / dropping networks spare the first page load, or nothing would open
        self._after_load = 0  # requests since the page loaded; every Nth fails, so a replay is repeatable

    def add(self, kind: str, detail: str) -> None:
        if (kind, detail) in self._seen:
            return
        self._seen.add((kind, detail))
        self.evidence.append(Evidence(f"E{len(self.evidence) + 1}", kind, detail, self.step))

    async def __aenter__(self) -> "Session":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch()
        extra = {"storage_state": str(self.storage_state)} if self.storage_state else {}
        context = self._context = await self._browser.new_context(**self.condition.context, **extra)
        await context.add_init_script(VITALS_JS)
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
        await self._wait_until_ready()
        if self.ready_text:  # the project says what "loaded" looks like: wait for it like a patient user
            for attempt in range(2):
                try:
                    await self.page.get_by_text(self.ready_text).first.wait_for(timeout=READY_TEXT_TIMEOUT_S * 1000)
                    break
                except Exception:
                    # A user refreshes a page that never finishes loading. Seen in CI: a cold Vite dev server
                    # reloads the page after bundling, and the second load hung on a spinner.
                    if attempt == 0:
                        try:
                            await self.page.reload(wait_until="load", timeout=60_000)
                        except Exception:  # still not there: let the twin see the screen as it is
                            break
                        await self._wait_until_ready()
        self._loaded = True
        return self

    async def _wait_until_ready(self) -> None:
        """Big apps keep loading after the load event (bundles, workers, a splash screen). A user waits for that,
        so the twin does too: network quiet and no spinner on screen, up to READY_TIMEOUT_S."""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=READY_TIMEOUT_S * 1000)
        except Exception:  # some apps poll forever; carry on after the timeout
            pass
        for _ in range(READY_TIMEOUT_S * 2):
            if not await self.page.evaluate(BUSY_JS):
                return
            await asyncio.sleep(0.5)

    async def __aexit__(self, *exc) -> None:
        # Release in-flight route handlers first: a handler still inside its latency sleep when the browser
        # closed left asyncio.run() waiting forever at shutdown (seen as an intermittent test hang).
        await self._context.unroute_all(behavior="ignoreErrors")
        await self._browser.close()
        await self._pw.stop()

    async def _route(self, route) -> None:
        if is_ours(route.request.url):  # the twin must never file complaints about itself
            await route.fulfill(status=204, body="")
            return
        net = self.condition.network or {}
        if self._loaded and net.get("drop_after_load"):
            await route.abort("internetdisconnected")
            return
        if self._loaded and net.get("fail_rate"):
            self._after_load += 1
            if self._after_load % round(1 / net["fail_rate"]) == 0:
                await route.abort("connectionreset")
                return
        if net.get("latency"):
            # CDP network throttling was silently ignored in tests (Playwright 1.63), so latency is
            # added per request here.
            await asyncio.sleep(net["latency"] / 1000)
        await route.continue_()

    def _listen(self) -> None:
        page = self.page
        page.on("request", self._on_request)
        page.on("requestfinished", self._on_finished)
        page.on("requestfailed", self._on_failed)
        page.on("response", self._on_response)
        page.on("framenavigated", self._on_navigated)
        page.on("console", lambda m: m.type == "error" and self.add("console_error", m.text[:200]))
        page.on("pageerror", lambda e: self.add("console_error", str(e)[:200]))

    def _on_request(self, request) -> None:
        self._track(+1)
        if not is_ours(request.url):
            self._requests += 1
        self._started[request] = time.monotonic()
        path = urlparse(request.url).path
        if request.method != "POST" or is_ours(request.url) or not PAYMENT_PATH.search(path):
            return
        now, body = time.monotonic(), request.post_data or ""
        for at, seen_path, seen_body in self._payments:
            if seen_path == path and seen_body == body and now - at < DUPLICATE_WINDOW_S:
                self.add("duplicate_request", f"POST {path} was sent twice within {now - at:.1f} s with the same "
                                              "data (the user would be charged twice)")
        self._payments.append((now, path, body))

    def _on_finished(self, request) -> None:
        self._track(-1)
        took = time.monotonic() - self._started.pop(request, time.monotonic())
        if took > SLOW_REQUEST_S and not is_ours(request.url):
            self.add("slow_request", f"{request.method} {urlparse(request.url).path} took {took:.0f} s")

    def _on_navigated(self, frame) -> None:
        if frame != self.page.main_frame:
            return
        now, url = time.monotonic(), frame.url
        self._navigations.append((now, url))
        times, window = REDIRECT_LOOP
        if sum(1 for t, u in self._navigations if u == url and now - t < window) >= times:
            self.add("redirect_loop", f"{urlparse(url).path} loaded {times} times in under {window:.0f} s")

    def _track(self, delta: int) -> None:
        self._inflight = max(0, self._inflight + delta)

    def _on_failed(self, request) -> None:
        self._track(-1)
        self._started.pop(request, None)
        if is_ours(request.url):
            return
        self.add("request_failed", f"{request.method} {urlparse(request.url).path} failed ({request.failure})")

    async def _on_response(self, response) -> None:
        if is_ours(response.url):
            return
        path = urlparse(response.url).path
        if response.status >= 400:
            self.add("http_error", f"{response.request.method} {path} returned HTTP {response.status}")
        if "json" not in response.headers.get("content-type", ""):
            return
        try:
            body = await response.json()
        except Exception:  # body can vanish if the page navigates; nothing to compare then
            return
        if isinstance(body, dict):
            for key in MONEY_KEYS:
                value = body.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self._record_amount(path, key, value)

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
        self._labels = {e["idx"]: e["label"] for e in obs["elements"]}
        self._layout(obs)
        self._language(obs)
        self._loading(obs)
        await self._own_checks()
        if self.condition.keyboard_only:
            if obs["focus"] and not obs["focus"]["outline"]:
                self.add("focus_invisible", f"keyboard focus is on '{obs['focus']['label']}' but nothing shows where")
            for label in obs["unreachable"]:
                self.add("not_keyboard_reachable", f"'{label}' looks clickable but Tab never reaches it")
        if self.condition.screen_reader:
            obs["aria"] = await self.page.locator("body").aria_snapshot()
            for u in obs["unnamed"]:
                self.add("unclear_name", f"a {u['tag']}{at(u)} is announced only as '{u['label'] or '(nothing)'}', "
                                         "which does not say what it does")
        if self.condition.screen_reader or self.condition.keyboard_only or self.condition.audit:
            for v in await self._axe():
                self.add("a11y_violation", f"{v['id']}: {v['help']} ({', '.join(v['targets'])})")
        return obs

    async def _own_checks(self) -> None:
        """A team's own rules ("invoice total = sum of lines"), run like the built-in collectors."""
        for name, js in self.checks.items():
            try:
                problems = await self.page.evaluate(js)
            except Exception as e:  # a broken check must say so, not hide a bug
                problems = [f"the check itself failed: {str(e).splitlines()[0][:150]}"]
            for p in problems or []:
                self.add(f"check:{name}", str(p.get("detail", p) if isinstance(p, dict) else p)[:300])

    def _layout(self, obs: dict) -> None:
        for o in obs["offscreen"]:
            self.add("offscreen_control", f"'{o['label']}'{at(o)} is outside the screen (left={o['left']}px, screen={o['vw']}px)")
        for c in obs["covered"]:
            self.add("covered_control", f"'{c['label']}'{at(c)} is on screen but covered by {c['by']}, so a tap hits that instead")
        for c in obs["clipped"]:
            self.add("clipped_text", f"'{c['label']}'{at(c)} is cut off: its text needs {c['needs']}px but has {c['has']}px")
        if obs["overflow"] > 2:
            self.add("page_overflow", f"the page is {obs['overflow']}px wider than the {obs['vw']}px screen and scrolls sideways")
        for src in obs["brokenImages"]:
            self.add("broken_image", f"image '{src[:120]}' did not load")
        vitals = obs.get("vitals") or {}
        if vitals.get("lcp", 0) > POOR_LCP_MS:
            self.add("slow_page", f"main content appeared after {vitals['lcp'] / 1000:.1f} s (poor is over 4 s)")
        if vitals.get("cls", 0) > POOR_CLS:
            self.add("layout_shift", f"the page jumped while loading (shift score {vitals['cls']:.2f}, poor is over 0.25)")

    def _language(self, obs: dict) -> None:
        """Text the user can't read, on a page that otherwise speaks their language."""
        locale = self.condition.locale
        want = base(locale)
        if not locale or want == "en":
            return
        if base(obs["lang"]) != want and detect(obs["text"])[0] != want:
            return  # the site is not translated into this language at all: a product gap, not this bug
        for alert in obs["alerts"]:
            why = not_in(alert, locale)
            if why:
                self.add("language_mismatch", f"message '{alert[:120]}' is {why}")
        if self.condition.rtl and obs["dir"] != "rtl":
            self.add("rtl_missing", f"the page is in '{want}', a right-to-left language, but lays out left-to-right")

    def _loading(self, obs: dict) -> None:
        now = time.monotonic()
        current = set(obs["busy"])
        self._busy_since = {k: v for k, v in self._busy_since.items() if k in current}
        for key in current:
            since = self._busy_since.setdefault(key, now)
            if now - since > STUCK_LOADING_S:
                self.add("stuck_loading", f"a loading indicator ({key}) has been on screen for over {STUCK_LOADING_S} s")

    async def _axe(self) -> list[dict]:
        if not await self.page.evaluate("typeof axe !== 'undefined'"):
            await self.page.add_script_tag(path=str(AXE_JS))
        return await self.page.evaluate(AXE_RUN_JS)

    async def act(self, action: dict) -> str:
        """Run one action. Returns 'ok' or a short error the model can react to."""
        self.step += 1
        page, kind = self.page, action.get("type")
        try:
            idx = int(action.get("target", -1))
        except (TypeError, ValueError):
            idx = -1
        self.last_target = self._labels.get(idx) if kind in ("click", "fill") else action.get("name")
        self.last_idx = idx if kind in ("click", "fill") and idx >= 0 else None
        if self.condition.keyboard_only and kind in ("click", "fill", "click_role", "fill_role"):
            return "error: this user has no mouse; use press (Tab, Enter, Space) and type"
        taps = kind in ("click", "click_role", "click_css") or (kind == "press" and action.get("key") in ("Enter", "Space"))
        opened, self._opened = self._opened, None
        before = await self._fingerprint() if taps else None
        requests_before = self._requests
        try:
            if kind == "click":
                await tap(page.locator(f'[data-bc-idx="{int(action["target"])}"]'), action)
            elif kind == "fill":
                field = page.locator(f'[data-bc-idx="{int(action["target"])}"]')
                await field.fill(str(action["text"]), timeout=5000)
                await self._remember_typed(field, self.last_target, str(action["text"]))
            elif kind in ("click_role", "fill_role"):
                if not action.get("name"):
                    return "error: a screen reader cannot use a control without a name"
                target = page.get_by_role(action["role"], name=action["name"]).first
                position = await target.get_attribute("data-bc-idx", timeout=2000)
                self.last_idx = int(position) if position and position.isdigit() else None
                if kind == "click_role":
                    await target.click(timeout=5000)
                else:
                    await target.fill(str(action["text"]), timeout=5000)
            elif kind == "press":
                key = str(action.get("key", ""))
                if key not in KEYS:
                    return f"error: key must be one of {sorted(KEYS)}"
                highlighted = await page.evaluate(HIGHLIGHTED_JS) if key == "Enter" else None
                await page.keyboard.press(key)
                if highlighted:
                    await self._check_choice(highlighted)
            elif kind == "type":
                await page.keyboard.type(str(action.get("text", "")), delay=30)
            elif kind == "click_css":  # scripted tests only
                await tap(page.locator(action["selector"]).first, action)
            elif kind == "fill_css":  # scripted tests only
                field = page.locator(action["selector"]).first
                await field.fill(str(action["text"]), timeout=5000)
                await self._remember_typed(field, action["selector"], str(action["text"]))
            elif kind == "goto":  # open another path of the same site (deep links in complaints, guards)
                await page.goto(self.base_url.rstrip("/") + "/" + str(action.get("path", "")).lstrip("/"))
            elif kind in ("scroll", "swipe"):
                # From the middle of the screen: at (0, 0) the wheel hits the top bar and inner panels never move.
                size = page.viewport_size or {"width": 800, "height": 600}
                await page.mouse.move(size["width"] / 2, size["height"] / 2)
                await page.mouse.wheel(0, -600 if action.get("direction") == "up" else 600)
            elif kind == "wait":
                await asyncio.sleep(min(int(action.get("ms", 1000)), 10_000) / 1000)
            else:
                return f"error: unknown action type {kind!r}"
        except Exception as e:  # report to the model; a failed click is information, not a crash
            await self._blocked(action, kind, str(e), opened)
            return f"error: {str(e).splitlines()[0][:200]}"
        await self.settle()
        if kind not in ("fill", "fill_role", "fill_css", "type"):
            await self._check_typed(self.last_target or action.get("selector") or action.get("key") or "a control")
        if before is not None and await self._fingerprint() == before and self._requests == requests_before:
            name = self.last_target or action.get("selector") or action.get("key") or "a control"
            self.add("no_response", f"tapped '{name}' but nothing happened: no change on screen, no request sent")
        elif taps:
            self._opened = self.last_target or action.get("name") or action.get("selector")
        return "ok"

    async def _element(self) -> str:
        """' (<input type="date">)' for the control last acted on, or '' when it cannot be read."""
        if self.last_idx is None:
            return ""
        try:
            el = self.page.locator(f'[data-bc-idx="{self.last_idx}"]').first
            return f" ({await el.evaluate(ELEMENT_JS, timeout=2000)})"
        except Exception:
            return ""

    async def _blocked(self, action: dict, kind: str, error: str, opened: str | None = None) -> None:
        """A tap the user could not make is evidence too: Playwright says what got in the way."""
        if kind not in ("click", "click_role", "click_css", "fill", "fill_role"):
            return
        name = self.last_target or action.get("name") or action.get("selector")
        if not name:
            return  # a blocked tap on an unknown control proves nothing about any complaint; the twin still sees the error
        blocker = INTERCEPTS.search(error)
        if blocker and name == opened:
            return  # the last tap on this control opened something that now covers it: a menu working as made
        if blocker:
            self.add("tap_blocked", f"tapping '{name}'{await self._element()} hit {blocker.group(1)[:120]} instead")
        elif "not visible" in error or "not enabled" in error or "not stable" in error or "Timeout" in error:
            self.add("tap_blocked",
                     f"'{name}'{await self._element()} could not be tapped: it never became visible, enabled and still")

    async def _check_choice(self, highlighted: dict) -> None:
        """Enter on a highlighted option must pick that option (ARIA combobox pattern)."""
        await asyncio.sleep(0.3)
        try:
            value = await self.page.evaluate(CHOSEN_JS, highlighted["field"])
        except Exception:
            return
        if value is not None and highlighted["option"] and highlighted["option"].lower() not in value.lower():
            self.add("wrong_option_chosen", f"'{highlighted['option']}' was highlighted when Enter was pressed, "
                                            f"but the field now holds '{value[:60]}'")

    async def _remember_typed(self, field, name: str | None, text: str) -> None:
        if text.strip():
            try:
                self._typed.append((await field.element_handle(timeout=2000), name or "a field", text))
            except Exception:  # the field went away at once; nothing to watch
                pass

    async def _check_typed(self, tapped: str) -> None:
        """What the user typed must survive tapping something else ("I typed the amount, tapped Cleared, it's gone")."""
        still = []
        for handle, name, text in self._typed:
            try:
                if not await handle.evaluate("e => e.isConnected"):
                    continue  # the form was closed or replaced on purpose (saved, navigated): not this bug
                value = (await handle.input_value()).strip()
            except Exception:
                continue
            if value in ("", "0", "0.00", "0,00") and text.strip() not in ("0", "0.00"):
                self.add("typed_value_lost", f"'{name}' held '{text[:40]}' the user typed; after tapping '{tapped}' it "
                                             f"shows '{value or '(empty)'}'")
                continue
            still.append((handle, name, text))
        self._typed = still

    async def _fingerprint(self) -> str | None:
        try:
            return await self.page.evaluate(FINGERPRINT_JS)
        except Exception:  # the page navigated mid-check: something clearly happened
            return None
