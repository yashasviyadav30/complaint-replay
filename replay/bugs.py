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
        4, "slow_3g_android", "Pay button pushed off-screen on small phones",
        "static/style.css",
        ".pay-row { display: flex; flex-wrap: wrap;",
        ".pay-row { display: flex; flex-wrap: nowrap; min-width: 560px;",
        "I added everything to my cart but there is no button to pay. How am I supposed to order??",
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
        15, "fast_desktop", "Coupon shown in cart but not applied at payment",
        "app.py",
        'return {"order_id": "BS-1042", "charged": total}',
        'return {"order_id": "BS-1042", "charged": subtotal}',
        "Applied SAVE10, the cart showed the discounted total, but I was charged the full price!",
    ),
)
BUGS_BY_ID = {b.id: b for b in BUGS}


def reset_workspace() -> Path:
    shutil.rmtree(WORK_SHOP, ignore_errors=True)
    shutil.copytree(CLEAN_SHOP, WORK_SHOP, ignore=shutil.ignore_patterns("__pycache__"))
    return WORK_SHOP


def inject(bug: Bug, shop: Path = WORK_SHOP) -> None:
    path = shop / bug.file
    text = path.read_text(encoding="utf-8")
    if text.count(bug.find) != 1:
        raise ValueError(f"bug {bug.id}: expected exactly one match in {bug.file}")
    path.write_text(text.replace(bug.find, bug.replace), encoding="utf-8")
