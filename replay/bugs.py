"""The bug library: small, realistic bugs injected into a copy of BadShop."""

import shutil
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLEAN_SHOP = ROOT / "badshop"
WORK_SHOP = ROOT / "workspace" / "badshop"


@dataclass(frozen=True)
class Bug:
    id: int
    condition: str
    title: str
    file: str  # relative to the shop root
    find: str
    replace: str
    complaint: str


BUGS = (
    Bug(
        1, "slow_3g_android", "OTP request gives up after 4 seconds",
        "static/config.js", "OTP_TIMEOUT_MS: 30000", "OTP_TIMEOUT_MS: 4000",
        "OTP never comes!! Tried 3 times on my phone, it just says something went wrong. Useless app",
    ),
    Bug(
        3, "slow_3g_android", "Pay can be tapped twice while paying, charging twice",
        "static/app.js",
        '  if ($("pay").dataset.busy) return; // a second tap while paying must not create a second order\n',
        "",
        "I pressed Pay and nothing happened so I pressed it again. Now I see two orders and two charges!!",
    ),
    Bug(
        4, "slow_3g_android", "Pay button pushed off-screen on small phones",
        "static/style.css",
        ".pay-row { display: flex; flex-wrap: wrap;",
        ".pay-row { display: flex; flex-wrap: nowrap; min-width: 560px;",
        "I added everything to my cart but there is no button to pay. How am I supposed to order??",
    ),
    Bug(
        16, "elderly", "OTP expires after 10 seconds, too soon for a slow reader",
        "app.py", "OTP_VALID_S = 300", "OTP_VALID_S = 10",
        "By the time I find the code in my messages and type it in, it says the code has expired. I tried three "
        "times and still cannot log in.",
    ),
    Bug(
        17, "train", "A retry after a dropped signal charges twice: every tap makes a new payment key",
        "static/app.js", "state.payKey ||= crypto.randomUUID();", "state.payKey = crypto.randomUUID();",
        "I paid on the train, the network dropped and the app said something went wrong. I tapped Pay again and "
        "now I have two orders and the money was taken twice!",
    ),
    Bug(
        7, "hindi", "Wrong-OTP error shown only in English",
        "static/app.js",
        'return showLoginError(t("invalidOtp"));',
        'return showLoginError("Invalid OTP. Please try again.");',
        "पूरी ऐप हिंदी में है लेकिन OTP गलत होने पर अंग्रेज़ी में कुछ लिखा आता है, समझ नहीं आया क्या करूँ",
    ),
    Bug(
        10, "screen_reader", "Cart button has no accessible name",
        "static/index.html", 'aria-label="Cart" hidden', "hidden",
        "I use a screen reader. After adding items I cannot find the cart anywhere, it just says 'button'.",
    ),
    Bug(
        13, "elderly", "Pay button lost when text is zoomed to 200%",
        "static/style.css",
        ".pay-row { display: flex; flex-wrap: wrap;",
        ".pay-row { display: flex; flex-wrap: nowrap; min-width: 280px;",
        "I made the letters bigger on my phone because I cannot read small text. Now there is no pay button anywhere.",
    ),
    Bug(
        15, "fast_desktop", "Coupon shown in cart but not applied at payment",
        "app.py",
        'order = {"order_id": f"BS-{1042 + len(orders)}", "charged": total}',
        'order = {"order_id": f"BS-{1042 + len(orders)}", "charged": subtotal}',
        "Applied SAVE10, the cart showed the discounted total, but I was charged the full price!",
    ),
)
BUGS_BY_ID = {b.id: b for b in BUGS}


LIVE_SHOP = ROOT / "workspace" / "live" / "badshop"  # the live service's copy, never touched by CLI or tests


def reset_workspace(dest: Path = WORK_SHOP) -> Path:
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(CLEAN_SHOP, dest, ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def inject(bug: Bug, shop: Path = WORK_SHOP) -> None:
    path = shop / bug.file
    text = path.read_text(encoding="utf-8")
    if text.count(bug.find) != 1:
        raise ValueError(f"bug {bug.id}: expected exactly one match in {bug.file}")
    path.write_text(text.replace(bug.find, bug.replace), encoding="utf-8")
