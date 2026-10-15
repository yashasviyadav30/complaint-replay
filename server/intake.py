"""What happens to a complaint before anything else sees it: personal data masked, language tagged, ranked.

Masking runs before storage and before any model call. `\\d` matches digits in every script
(Devanagari ०-९, Arabic-Indic ٠-٩), so numbers typed on any phone keyboard are caught.
"""

import hashlib
import hmac
import os
import re
import secrets
import time
import unicodedata
from pathlib import Path

PII_PATTERNS = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,30}\b"), "[iban]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[tax id]"),  # Indian PAN
    (re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)"), "[number]"),  # cards and long account or order numbers
    (re.compile(r"(?<!\d)\d{4}\s\d{4}\s\d{4}(?!\d)"), "[id number]"),  # Aadhaar as printed
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[phone]"),  # Indian mobile
    (re.compile(r"\+\d{1,3}[\s-]?(?:\(?\d+\)?[\s-]?){2,5}\d"), "[phone]"),  # any international number
    (re.compile(r"(?<!\d)\d{12,}(?!\d)"), "[number]"),
)

# How bad a proven problem is, for ranking the board. Money and dead ends first.
SEVERITY = {
    "duplicate_request": 5, "amount_mismatch": 5, "redirect_loop": 4,
    "request_failed": 3, "http_error": 3, "offscreen_control": 3, "covered_control": 3, "stuck_loading": 3,
    "not_keyboard_reachable": 3, "language_mismatch": 2, "rtl_missing": 2, "a11y_violation": 2, "unclear_name": 2,
    "clipped_text": 2, "page_overflow": 2, "focus_invisible": 2, "broken_image": 1, "slow_page": 1,
    "slow_request": 1, "layout_shift": 1, "console_error": 1,
}


ANY_DIGIT = re.compile(r"\d")


def mask_pii(text: str) -> str:
    # Digits typed in any script (Devanagari ९, Arabic-Indic ٩) become ASCII first, so every pattern sees them.
    text = ANY_DIGIT.sub(lambda m: str(unicodedata.digit(m.group())), text)
    for pattern, token in PII_PATTERNS:
        text = pattern.sub(token, text)
    return text


def impact(case: dict) -> int:
    """People affected x how bad it is. Before a replay proves anything, every report counts as 1."""
    rep = case.get("replay") or {}
    cited = [e["kind"] for e in rep.get("evidence", []) if e["id"] in rep.get("cited", [])]
    return case.get("reports", 1) * max((SEVERITY.get(k, 1) for k in cited), default=1)


def complaint_for_model(record: dict) -> str:
    said = record["text"] if record["kind"] == "spoken" else f"(The user typed nothing. Silent signal: {record['text']})"
    trail = "; ".join(record["breadcrumbs"][-6:])
    return f"{said}\nPage: {record['page']}." + (f" What the user did just before: {trail}." if trail else "")


# --- signed values (login cookie, per-case callback tokens) ---

SECRET_FILE = Path(__file__).resolve().parent.parent / "results" / "secret.key"


def server_secret() -> bytes:
    if os.getenv("SECRET_KEY"):
        return os.environ["SECRET_KEY"].encode()
    if not SECRET_FILE.exists():
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
    return SECRET_FILE.read_text(encoding="utf-8").strip().encode()


SESSION_S = 7 * 24 * 3600


def sign(value: str) -> str:
    return value + "." + hmac.new(server_secret(), value.encode(), hashlib.sha256).hexdigest()[:32]


def unsign(signed: str) -> str | None:
    value = signed.rpartition(".")[0]
    return value if value and hmac.compare_digest(sign(value).encode(), signed.encode()) else None


def session_value(login: str) -> str:
    """A login cookie: who, and since when. Different prefix from case tokens, so one can't pose as the other."""
    return sign(f"session:{login}:{int(time.time())}")


def session_login(cookie: str) -> str | None:
    kind, _, rest = (unsign(cookie) or "").partition(":")
    login, _, issued = rest.rpartition(":")
    if kind != "session" or not login or not issued.isdigit() or time.time() - int(issued) > SESSION_S:
        return None
    return login
