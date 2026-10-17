"""A short film of a replay: one frame per step, each with a caption, saved as an animated GIF.

GIFs play inside GitHub pull requests, the dashboard and the reporter's status page; video files don't.
Captions are drawn on the image, never into the page, so they can't change what the evidence checks see.
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 360  # px: a phone screen stays readable, a desktop one shrinks to fit a PR column
MAX_HEIGHT = 720
CAPTION_PX = 15
PAD = 10
FRAME_MS = 1400
LAST_FRAME_MS = 4500  # the frame that shows the problem (or its absence) stays longest
BAND = (17, 24, 39)
ALERT = (153, 27, 27)
GOOD = (21, 128, 61)

HIGHLIGHT = (250, 204, 21)
# (PNG screenshot, caption, "" | "alert" | "good", box or None). The box marks the control about to be used, as
# fractions of the screen (x, y, width, height), so it lands right whatever the device's pixel density.
Frame = tuple[bytes, str, str, tuple[float, float, float, float] | None]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return [*lines, line][:5] if line else lines[:5]


def _frame(png: bytes, caption: str, tone: str, box, font) -> Image.Image:
    shot = Image.open(io.BytesIO(png)).convert("RGB")
    shot = shot.resize((WIDTH, max(1, round(shot.height * WIDTH / shot.width))))
    if box:
        x, y, w, h = (box[0] * shot.width, box[1] * shot.height, box[2] * shot.width, box[3] * shot.height)
        ImageDraw.Draw(shot).rectangle((x - 3, y - 3, x + w + 3, y + h + 3), outline=HIGHLIGHT, width=3)
    shot = shot.crop((0, 0, WIDTH, min(shot.height, MAX_HEIGHT)))
    measure = ImageDraw.Draw(shot)
    lines = _wrap(measure, caption, font, WIDTH - 2 * PAD)
    line_h = CAPTION_PX + 5
    band = len(lines) * line_h + 2 * PAD
    out = Image.new("RGB", (WIDTH, shot.height + band), {"alert": ALERT, "good": GOOD}.get(tone, BAND))
    out.paste(shot, (0, 0))
    draw = ImageDraw.Draw(out)
    for i, line in enumerate(lines):
        draw.text((PAD, shot.height + PAD + i * line_h), line, fill=(255, 255, 255), font=font)
    return out


def write_gif(frames: list[Frame], path: Path) -> Path | None:
    """Save the frames as a looping GIF at `path`; None when there is nothing to show."""
    if not frames:
        return None
    font = ImageFont.load_default(size=CAPTION_PX)
    images = [_frame(png, caption, tone, box, font) for png, caption, tone, box in frames]
    height = max(im.height for im in images)
    padded = []
    for im in images:  # every GIF frame must have the same size
        canvas = Image.new("RGB", (WIDTH, height), BAND)
        canvas.paste(im, (0, 0))
        padded.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
    path.parent.mkdir(parents=True, exist_ok=True)
    padded[0].save(path, save_all=True, append_images=padded[1:], loop=0, optimize=True,
                   duration=[FRAME_MS] * (len(padded) - 1) + [LAST_FRAME_MS])
    return path


def describe(action: dict, target: str | None) -> str:
    """'tap 'Pay'', 'type '100' into 'Amount'', 'press Tab ×3': what the twin did, in a user's words."""
    kind, name = action.get("type", ""), target or action.get("name") or action.get("selector") or ""
    times = f" ×{action['times']}" if int(action.get("times", 1) or 1) > 1 else ""
    if kind in ("click", "click_role", "click_css"):
        return f"tap '{name}'{times}"
    if kind in ("fill", "fill_role", "fill_css"):
        return f"type '{str(action.get('text', ''))[:30]}' into '{name}'"
    if kind in ("press", "tab"):
        return f"press {action.get('key', 'Tab')}{times}"
    if kind == "type":
        return f"type '{str(action.get('text', ''))[:30]}'"
    if kind == "goto":
        return f"open {action.get('path', '/')}"
    return {"scroll": "scroll", "swipe": "swipe", "wait": "wait"}.get(kind, kind)
