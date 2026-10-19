"""Real user conditions, enforced by the browser rather than role-played.

A condition is built from what the widget saw on the real user's device (`twin_condition`), or by name
from the CLI (`profile`): any of Playwright's 207 device profiles, a network profile, any locale and
timezone, dark mode, forced colors, reduced motion, text zoom, keyboard only, or a screen reader.
"""

import json
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path

from replay.langid import RTL, base

ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 11; Redmi 9A) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
)
# 3 s of added latency per request: a bad but common mobile connection.
SLOW_3G = {"latency": 3000}
PHONE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}
DEVICES_FILE = Path(__file__).with_name("devices.json")  # Playwright's device catalog, saved

# Added latency per request (ms), share of requests that fail, or a connection that drops after the page loads.
# ponytail: latency and failures only; add bandwidth caps if a real bug needs slow downloads of big files.
NETWORKS: dict[str, dict | None] = {
    "wifi": None,
    "4g": {"latency": 150},
    "3g": {"latency": 1500},
    "slow-3g": {"latency": 3000},
    "2g": {"latency": 5000},
    "satellite": {"latency": 800},
    "flaky": {"latency": 400, "fail_rate": 0.25},
    "drops": {"latency": 200, "drop_after_load": True},
}
SLOW_TYPES = {"slow-2g": 5000, "2g": 3000, "3g": 1500}  # added latency (ms) when only the type is known
MAX_TWIN_LATENCY_MS = 5000


@dataclass(frozen=True)
class Condition:
    key: str
    label: str
    persona: str
    context: dict = field(default_factory=dict)  # Playwright new_context kwargs
    network: dict | None = None
    cpu_slowdown: int = 1
    zoom: float = 1.0
    screen_reader: bool = False
    keyboard_only: bool = False
    max_steps: int = 20
    audit: bool = False  # run accessibility checks for every user (public-sector projects)
    engine: str = "chromium"  # "webkit": Safari's engine, for iPhones, iPads and Safari users
    slow: bool = False  # reads before each step and types key by key (older users): finds too-short timeouts

    @property
    def locale(self) -> str:
        return self.context.get("locale", "")

    @property
    def rtl(self) -> bool:
        return base(self.locale) in RTL


@cache
def devices() -> dict[str, dict]:
    return json.loads(DEVICES_FILE.read_text(encoding="utf-8"))


def device(name: str) -> tuple[str, dict]:
    """Look a device up by name, ignoring case: 'galaxy s9+', 'iPhone 15', 'Pixel 7'."""
    by_lower = {k.lower(): k for k in devices()}
    key = by_lower.get(name.lower())
    if not key:
        close = [k for k in devices() if name.lower() in k.lower()][:5]
        raise ValueError(f"unknown device {name!r}" + (f"; did you mean: {', '.join(close)}" if close else ""))
    # The engine is not a context option: profile() launches it (iPhones and iPads run in WebKit, Safari's engine).
    return key, {k: v for k, v in devices()[key].items() if k != "default_browser_type"}


def profile(device_name: str = "", network: str = "wifi", locale: str = "", timezone: str = "",
            color_scheme: str = "", reduced_motion: bool = False, forced_colors: bool = False,
            zoom: float = 1.0, screen_reader: bool = False, keyboard_only: bool = False,
            max_steps: int = 20) -> Condition:
    """A named set of conditions, for the CLI and for replaying a whole matrix of users."""
    if network not in NETWORKS:
        raise ValueError(f"unknown network {network!r}; one of: {', '.join(NETWORKS)}")
    context: dict = {"viewport": {"width": 1280, "height": 800}}
    parts = []
    engine = "chromium"
    if device_name:
        name, context = device(device_name)
        engine = devices()[name].get("default_browser_type", "chromium")
        parts.append(f"{name} ({context['viewport']['width']}x{context['viewport']['height']})"
                     + (", Safari" if engine == "webkit" else ""))
    else:
        parts.append("desktop 1280x800")
    if network != "wifi":
        parts.append(f"{network} network")
    for key, value, text in (("locale", locale, f"language {locale}"), ("timezone_id", timezone, f"timezone {timezone}"),
                             ("color_scheme", color_scheme, f"{color_scheme} mode")):
        if value:
            context[key] = value
            parts.append(text)
    if reduced_motion:
        context["reduced_motion"] = "reduce"
        parts.append("reduced motion")
    if forced_colors:
        context["forced_colors"] = "active"
        parts.append("high-contrast colors")
    if zoom != 1.0:
        parts.append(f"text zoomed to {zoom:.0%}")
    if keyboard_only:
        parts.append("keyboard only, no mouse")
    if screen_reader:
        parts.append("screen reader")
    persona = "A user on " + ", ".join(parts) + "."
    return Condition("custom", ", ".join(parts), persona, context, NETWORKS[network], zoom=zoom,
                     screen_reader=screen_reader, keyboard_only=keyboard_only, max_steps=max_steps, engine=engine)


def safari_engine(user_agent: str) -> bool:
    """Every browser on an iPhone or iPad is Safari's engine underneath; on a Mac, only Safari itself is."""
    if any(device in user_agent for device in ("iPhone", "iPad", "iPod")):
        return True
    return "Safari" in user_agent and not any(other in user_agent for other in ("Chrome", "Chromium", "Android", "Edg"))


def twin_condition(env: dict) -> Condition:
    """A browser setup that copies the conditions the widget captured from a real user."""
    vp = env["viewport"]
    mobile = bool(env.get("touch")) or "Mobile" in env.get("user_agent", "")
    lang = env.get("language") or "en"
    rtt = env.get("rtt_ms")
    latency = min(rtt, MAX_TWIN_LATENCY_MS) if rtt else SLOW_TYPES.get(env.get("effective_type") or "", 0)
    context = {"viewport": {"width": vp["width"], "height": vp["height"]}, "locale": lang,
               "is_mobile": mobile, "has_touch": mobile}
    if env.get("pixel_ratio"):
        context["device_scale_factor"] = env["pixel_ratio"]
    if env.get("user_agent"):
        context["user_agent"] = env["user_agent"]
    parts = [f"{vp['width']}x{vp['height']} {'phone' if mobile else 'screen'}", f"language {lang}"]
    if env.get("timezone"):
        context["timezone_id"] = env["timezone"]
        parts.append(f"timezone {env['timezone']}")
    if env.get("color_scheme") in ("dark", "light"):
        context["color_scheme"] = env["color_scheme"]
        parts.append(f"{env['color_scheme']} mode")
    if env.get("reduced_motion"):
        context["reduced_motion"] = "reduce"
        parts.append("reduced motion")
    if env.get("forced_colors"):
        context["forced_colors"] = "active"
        parts.append("high-contrast colors")
    if latency:
        parts.append(f"{env.get('effective_type') or 'slow'} network (+{latency} ms per request)")
    engine = "webkit" if safari_engine(env.get("user_agent", "")) else "chromium"
    if engine == "webkit":
        parts.append("Safari")
    return Condition(
        "twin", ", ".join(parts[:2]), "The real user who reported this: " + ", ".join(parts) + ".",
        context, network={"latency": latency} if latency else None, engine=engine,
    )


def with_needs(cond: Condition, needs: dict) -> Condition:
    """Add what the user said about themselves (screen reader, keyboard only, larger text) to measured conditions."""
    words = [w for w, on in (("use a screen reader", needs.get("screen_reader")),
                             ("use only a keyboard", needs.get("keyboard_only")),
                             (f"have text zoomed to {needs.get('zoom', 1):.0%}", needs.get("zoom", 1) > 1)) if on]
    if not words:
        return cond
    return replace(cond, persona=cond.persona.rstrip(".") + "; the user says they " + " and ".join(words) + ".",
                   screen_reader=cond.screen_reader or bool(needs.get("screen_reader")),
                   keyboard_only=cond.keyboard_only or bool(needs.get("keyboard_only")),
                   zoom=max(cond.zoom, needs.get("zoom", 1.0) or 1.0))


CONDITIONS = {
    c.key: c
    for c in (
        Condition(
            "fast_desktop", "Fast desktop", "A developer on a fast laptop with good Wi-Fi.",
            {"viewport": {"width": 1280, "height": 800}},
        ),
        Condition(
            "slow_3g_android", "Slow 3G + cheap Android",
            "A user on a cheap Android phone (360 px screen) with a slow 3G connection.",
            {"viewport": {"width": 360, "height": 740}, "is_mobile": True, "has_touch": True,
             "device_scale_factor": 2, "user_agent": ANDROID_UA},
            # No CPU slowdown: Chrome's CPU throttling made page timers fire unpredictably late,
            # so a real timeout bug reproduced only some of the time.
            network=SLOW_3G,
        ),
        Condition(
            "hindi", "Hindi speaker", "A user whose phone is set to Hindi and who reads Hindi, not English.",
            {**PHONE, "locale": "hi-IN"},
        ),
        Condition(
            "arabic", "Arabic speaker", "A user whose phone is set to Arabic (right-to-left) and who reads Arabic.",
            {**PHONE, "locale": "ar-EG", "timezone_id": "Africa/Cairo"},
        ),
        Condition(
            "screen_reader", "Screen-reader user",
            "A blind user with a screen reader. Only controls with an accessible name can be used.",
            {"viewport": {"width": 1280, "height": 800}}, screen_reader=True,
        ),
        Condition(
            "keyboard", "Keyboard-only user",
            "A user who cannot use a mouse (motor impairment) and moves with Tab, Shift+Tab, Enter and Space.",
            {"viewport": {"width": 1280, "height": 800}}, keyboard_only=True, max_steps=30,
        ),
        Condition(
            "elderly", "Elderly first-time user",
            "An elderly first-time smartphone user with 200% zoom who reads slowly, types one key at a time, and "
            "gives up after a few confusing steps.",
            dict(PHONE), zoom=2.0, max_steps=8, slow=True,
        ),
        Condition(
            "iphone", "iPhone Safari",
            "A user on an iPhone 15 in Safari, on 4G. Safari's engine (WebKit) behaves differently from Chrome's.",
            device("iPhone 15")[1], network=NETWORKS["4g"], engine="webkit",
        ),
        Condition(
            "flaky_network", "Flaky mobile network",
            "A commuter on a train whose connection keeps dropping: a quarter of requests fail.",
            dict(PHONE), network=NETWORKS["flaky"],
        ),
    )
}
