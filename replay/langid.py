"""Which language (and script) a piece of text is in. Runs on the CPU, no API call.

Model: fastText lid.176 (176 languages, under 1 MB, CC BY-SA 3.0), downloaded on first use.
Set LID_MODEL to a bigger fastText model, for example GlotLID v3 (2102 labels, 1.7 GB), to swap it in.
Romanised Hindi ("otp nahi aa raha") is not a label in lid.176, so it comes back as a low-confidence guess.
"""

import os
import unicodedata
import urllib.request
from collections import Counter
from functools import cache
from pathlib import Path

LID176_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
CACHE = Path(os.getenv("CRP_CACHE") or Path.home() / ".cache" / "complaint-replay")
MIN_LETTERS = 12  # shorter strings ("Pay", "OK") are too short to judge the language of
MIN_CONFIDENCE = 0.6

# Languages whose script is not Latin. Anything missing here is assumed to use Latin script.
SCRIPTS = {
    "hi": "DEVANAGARI", "mr": "DEVANAGARI", "ne": "DEVANAGARI", "sa": "DEVANAGARI",
    "ar": "ARABIC", "fa": "ARABIC", "ur": "ARABIC", "ps": "ARABIC", "sd": "ARABIC", "ug": "ARABIC",
    "he": "HEBREW", "yi": "HEBREW",
    "ru": "CYRILLIC", "uk": "CYRILLIC", "bg": "CYRILLIC", "be": "CYRILLIC", "mk": "CYRILLIC", "kk": "CYRILLIC",
    "ky": "CYRILLIC", "mn": "CYRILLIC", "sr": "CYRILLIC",
    "el": "GREEK", "th": "THAI", "lo": "LAO", "km": "KHMER", "my": "MYANMAR", "ka": "GEORGIAN", "hy": "ARMENIAN",
    "am": "ETHIOPIC", "si": "SINHALA", "bn": "BENGALI", "as": "BENGALI", "ta": "TAMIL", "te": "TELUGU",
    "gu": "GUJARATI", "pa": "GURMUKHI", "kn": "KANNADA", "ml": "MALAYALAM", "or": "ORIYA",
    "zh": "CJK", "ja": "CJK", "ko": "HANGUL",
}
RTL = {"ar", "fa", "ur", "ps", "sd", "ug", "he", "yi", "dv", "ckb"}
JAPANESE_KANA = ("HIRAGANA", "KATAKANA")


def base(locale: str) -> str:
    return (locale or "en").replace("_", "-").split("-")[0].lower()


def script_of(text: str) -> str | None:
    """The script most letters in `text` are written in (LATIN, DEVANAGARI, ARABIC, CJK, ...)."""
    counts: Counter[str] = Counter()
    for ch in text:
        if ch.isalpha():
            word = unicodedata.name(ch, "").split(" ")[0]
            counts["CJK" if word in JAPANESE_KANA or word == "CJK" else word] += 1
    return counts.most_common(1)[0][0] if counts else None


def expected_script(locale: str) -> str:
    return SCRIPTS.get(base(locale), "LATIN")


@cache
def _model():
    import fasttext  # fasttext-predict: inference only, prebuilt wheels

    path = Path(os.getenv("LID_MODEL") or CACHE / "lid.176.ftz")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(LID176_URL, path)
    return fasttext.load_model(str(path))


def detect(text: str) -> tuple[str, float]:
    """(language code, confidence). Codes are ISO 639-1 where the model has one ('en', 'hi', 'ar')."""
    labels, probs = _model().predict(" ".join(text.split()), k=1)
    code = labels[0].removeprefix("__label__").split("_")[0]  # GlotLID labels look like 'hin_Deva'
    return code, float(probs[0])


def not_in(text: str, locale: str) -> str | None:
    """Why `text` is not in the user's language, or None if it is (or it is too short to tell)."""
    want = base(locale)
    script = script_of(text)
    if script and script != expected_script(locale):
        return f"written in {script.title()} script, but the user reads '{want}'"
    if sum(ch.isalpha() for ch in text) < MIN_LETTERS:
        return None
    lang, conf = detect(text)
    if lang != want and len(lang) == 2 and conf >= MIN_CONFIDENCE:
        return f"looks like '{lang}' ({conf:.0%} sure), but the user reads '{want}'"
    return None
