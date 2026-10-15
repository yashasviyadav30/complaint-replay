"""Write a labelled complaint set in 20 languages with Nemotron. SYNTHETIC: machine-written, not real users.

Each language gets the same scenarios, so a test can check that "OTP never comes" in Tamil and in Spanish
land in the same group, and that triage (bug / confusion / feature request / spam) works across scripts.
Run: uv run python scripts/make_multilingual_set.py   -> data/complaints_multilingual.json
"""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from replay.llm import Chat, make_client, parse_json, pick_model  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "complaints_multilingual.json"
LANGUAGES = {
    "en": "English", "hi": "Hindi in Devanagari script",
    "hi-Latn": "Hinglish (Hindi written in Latin letters, mixed with English)",
    "ar": "Arabic", "ur": "Urdu", "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "mr": "Marathi", "es": "Spanish",
    "pt": "Brazilian Portuguese", "fr": "French", "de": "German", "id": "Indonesian", "sw": "Swahili", "tr": "Turkish",
    "vi": "Vietnamese", "ru": "Russian", "ja": "Japanese", "zh": "Simplified Chinese",
}
# What each complaint is about. "bug:*" ids are the groups duplicate detection must find across languages.
SCENARIOS = {
    "bug:otp": "the login OTP / code never arrives, an error appears after waiting",
    "bug:pay_missing": "there is no Pay button on their phone after adding items to the cart",
    "bug:double_charge": "they tapped Pay twice because nothing happened and were charged twice",
    "bug:coupon": "the coupon showed a discount in the cart but they were charged the full price",
    "bug:wrong_language": "an error message suddenly appears in English although the app is in their language",
    "bug:cart_screen_reader": "they use a screen reader and the cart button is only read as a number",
    "bug:stuck_loading": "the orders page shows a loading spinner forever",
    "ux_confusion": "nothing is broken, they just cannot find where to change their delivery address",
    "feature_request": "they wish the shop had a dark mode or cash on delivery",
    "spam": "an unrelated advert or a message with no complaint (e.g. 'hello', a link to buy followers)",
}
SYSTEM = """You write realistic customer complaints for testing software. Real people write short, emotional,
sometimes misspelled messages from a phone. Never mention that this is a test.
Reply with ONE JSON object and nothing else: {"items": [{"scenario": "<id>", "text": "<complaint>"}, ...]}"""
ATTEMPTS = 3


async def one_language(chat: Chat, code: str, name: str) -> list[dict]:
    wanted = "\n".join(f"- {sid}: {what} (write 2 different messages)" for sid, what in SCENARIOS.items())
    reply = await chat([{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": f"Write the messages in {name}. Scenarios:\n{wanted}"}])
    items = parse_json(reply).get("items", [])
    return [{"lang": code, "scenario": i["scenario"], "text": str(i["text"]).strip()}
            for i in items if i.get("scenario") in SCENARIOS and str(i.get("text", "")).strip()]


async def main() -> None:
    load_dotenv()
    client = make_client()
    chat = Chat(client, await pick_model(client))
    rows = []
    for code, name in LANGUAGES.items():
        got: list[dict] = []
        for _ in range(ATTEMPTS):
            try:
                got = await one_language(chat, code, name)
                break
            except ValueError as e:
                print(f"{code}: unreadable reply ({e}), retrying", flush=True)
        print(f"{code}: {len(got)} complaints", flush=True)
        rows += got
    OUT.write_text(json.dumps({
        "_about": "SYNTHETIC complaints written by NVIDIA Nemotron (scripts/make_multilingual_set.py), not real users. "
                  "scenario = what the complaint is about; bug:* ids are duplicate groups across languages.",
        "model": chat.model, "complaints": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(rows)} complaints to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
