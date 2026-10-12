"""Real user conditions, enforced by the browser rather than role-played."""

from dataclasses import dataclass, field

ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 11; Redmi 9A) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
)
# 3 s of added latency per request: a bad but common mobile connection.
SLOW_3G = {"latency": 3000}
PHONE = {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True}


@dataclass(frozen=True)
class Condition:
    key: str
    label: str
    persona: str
    context: dict = field(default_factory=dict)  # Playwright new_context kwargs
    network: dict | None = None  # CDP Network.emulateNetworkConditions
    cpu_slowdown: int = 1
    zoom: float = 1.0
    screen_reader: bool = False
    max_steps: int = 20

    @property
    def hindi(self) -> bool:
        return self.context.get("locale", "").startswith("hi")


SLOW_TYPES = {"slow-2g": 3000, "2g": 3000, "3g": 1500}  # added latency (ms) when only the type is known
MAX_TWIN_LATENCY_MS = 5000


def twin_condition(env: dict) -> Condition:
    """A browser setup that copies the conditions the widget captured from a real user."""
    vp = env["viewport"]
    mobile = bool(env.get("touch")) or "Mobile" in env.get("user_agent", "")
    lang = env.get("language") or "en"
    rtt = env.get("rtt_ms")
    latency = min(rtt, MAX_TWIN_LATENCY_MS) if rtt else SLOW_TYPES.get(env.get("effective_type") or "", 0)
    context = {"viewport": {"width": vp["width"], "height": vp["height"]}, "locale": lang,
               "is_mobile": mobile, "has_touch": mobile}
    if env.get("user_agent"):
        context["user_agent"] = env["user_agent"]
    parts = [f"{vp['width']}x{vp['height']} {'phone' if mobile else 'screen'}", f"language {lang}"]
    if latency:
        parts.append(f"{env.get('effective_type') or 'slow'} network (+{latency} ms per request)")
    return Condition(
        "twin", "Twin of the reporter", "The real user who reported this: " + ", ".join(parts) + ".",
        context, network={"latency": latency} if latency else None,
    )


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
            "screen_reader", "Screen-reader user",
            "A blind user with a screen reader. Only controls with an accessible name can be used.",
            {"viewport": {"width": 1280, "height": 800}}, screen_reader=True,
        ),
        Condition(
            "elderly", "Elderly first-time user",
            "An elderly first-time smartphone user with 200% zoom who gives up after a few confusing steps.",
            dict(PHONE), zoom=2.0, max_steps=8,
        ),
    )
}
