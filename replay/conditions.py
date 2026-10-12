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
