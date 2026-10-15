"""Builds index.html for the narrated explainer from narration.json + the voice files' real lengths.

Run: python build.py   (after generating assets/vo/<id>.wav, see README.md in this folder)
Scene length = voice length + LEAD + TAIL. Footage is slowed (never sped up) to fill its scene.
Subtitle and reveal timings are spread over each voice file by character count, so they are close, not exact.
"""

import html
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
LEAD, TAIL = 0.3, 0.6
MAX_SUB = 105  # characters per subtitle line group


def length(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout)


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s]


def chunks(sentence: str) -> list[str]:
    """Split a long sentence at commas/colons so a subtitle never runs past two lines."""
    parts, cur = [], ""
    for piece in re.split(r"(?<=[,:])\s+", sentence):
        if cur and len(cur) + 1 + len(piece) > MAX_SUB:
            parts.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}".strip()
    return parts + [cur]


def timed(text: str, start: float, dur: float) -> list[tuple[str, float, float]]:
    """(chunk, start, duration) spread over the voice by character count."""
    pieces = [c for s in sentences(text) for c in chunks(s)]
    total = sum(len(p) for p in pieces)
    out, t = [], start
    for p in pieces:
        d = dur * len(p) / total
        out.append((p, t, d))
        t += d
    return out


def sentence_starts(text: str, start: float, dur: float) -> list[float]:
    ss = sentences(text)
    total = sum(len(s) for s in ss)
    out, t = [], start
    for s in ss:
        out.append(t)
        t += dur * len(s) / total
    return out


E = html.escape

# Each scene maker gets (scene id, start, duration, sentence start times) and returns (html, animations).

def footage(clips):
    """clips: [(src, clip_length)] played back to back, slowed to fill the scene."""
    def make(sid, t0, dur, st):
        total = sum(c for _, c in clips)
        rate = min(1.0, total / dur)
        parts, t = [], t0
        for i, (src, clen) in enumerate(clips):
            d = clen / rate
            parts.append(f'<video id="{sid}-v{i}" class="clip footage" src="assets/{src}" data-start="{t:.2f}" '
                         f'data-duration="{d:.2f}" data-media-start="0" data-playback-rate="{rate:.3f}" '
                         f'data-track-index="0" muted playsinline></video>')
            t += d
        return "\n".join(parts), []
    return make


def shots(items):
    """items: [(img, alt, share)] shown back to back with a slow push-in."""
    def make(sid, t0, dur, st):
        total = sum(s for *_, s in items)
        parts, anims, t = [], [], t0
        for i, (img, alt, share) in enumerate(items):
            d = dur * share / total
            parts.append(f'<div id="{sid}-s{i}" class="clip frame" data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="0">'
                         f'<img src="assets/{img}" alt="{E(alt)}" /></div>')
            anims.append((f"push:#{sid}-s{i} img", t, d))
            t += d
        return "\n".join(parts), anims
    return make


def card(inner, reveals):
    """A slide; reveals: [(css selector inside the slide, sentence index or float offset in seconds)]."""
    def make(sid, t0, dur, st):
        anims = []
        for sel, at in reveals:
            if isinstance(at, tuple):  # (sentence index, extra seconds)
                when = st[at[0]] + at[1]
            else:
                when = st[at] if isinstance(at, int) else t0 + at
            anims.append((f"#{sid} {sel}", when))
        return f'<div id="{sid}" class="clip slide" data-start="{t0:.2f}" data-duration="{dur:.2f}" data-track-index="2">{inner}</div>', anims
    return make


def rows(items, cls="row"):
    return "".join(f'<li class="{cls} r{i}"><b>{E(a)}</b><span>{E(b)}</span></li>' for i, (a, b) in enumerate(items))


STEPS = [("1  Heard", "A typed complaint, or a silent signal like rage clicks"),
         ("2  Reproduced", "An AI twin repeats it in a real browser, under the user's conditions"),
         ("3  Proven", "Machine evidence only. No evidence, no verdict"),
         ("4  Fixed", "NVIDIA Nemotron writes the smallest fix, on a branch copy"),
         ("5  Fix proven", "The same twin replays the complaint on the fixed code"),
         ("6  Guarded", "The steps become a test: passes on the fix, fails on the old code")]
EVIDENCE = ["Failed request", "Server error", "Button off screen", "English error for a Hindi user",
            "Accessibility violation", "Money values disagree", "Payment sent twice"]
USERS = [("Slow 3G phone", "OTP request gives up after 4 seconds"),
         ("Small 360 px phone", "Pay button pushed off screen"),
         ("Hindi speaker", "Wrong-OTP error only in English"),
         ("Screen-reader user", "Cart button has no name"),
         ("Elderly user, 200% text", "Pay button lost"),
         ("Slow network, double tap", "Charged twice"),
         ("Fast desktop", "Coupon shown, not applied at payment")]
STACK = [("NVIDIA Nemotron 3 Super", "navigator, judge and fixer"),
         ("Nemotron Embed + Nemotron 3.5 Lightning", "group duplicate complaints"),
         ("Tavily", "research before each fix"),
         ("Playwright + axe-core", "real browser, accessibility checks"),
         ("One OpenAI-compatible client", "Nebius Token Factory is one setting")]

SCENES = {
    "title": card('<p class="kicker">Nebius x NVIDIA Global AI Hackathon · explainer</p><h1 class="big">Complaint Replay</h1>'
                  '<p class="lede">Complaint in. Proof, fix and test out.</p>',
                  [(".kicker", 0.2), (".big", 0.5), (".lede", 1.2)]),
    "problem": card('<p class="quote">"OTP never comes!"</p><p class="lede l1">Developer, fast laptop, good Wi-Fi: it works. Closed as "can\'t reproduce".</p>'
                    '<p class="stat-line l2"><b>13-24%</b> of bug reports are never reproduced <span>(ICSME 2020)</span></p>'
                    '<p class="lede l3">The bug only shows up on the customer\'s slow phone, small screen or language.</p>',
                    [(".quote", 1), (".l1", 2), (".l2", 5), (".l3", 6)]),
    "steps": card('<p class="kicker">Six steps</p><ol class="steps">' + rows(STEPS) + '</ol>',
                  [(".kicker", 0.2)] + [(f".r{i}", i + 1) for i in range(6)]),
    "break": footage([("s-break.mp4", 8)]),
    "shop": footage([("s-shopA.mp4", 11), ("s-shopB.mp4", 6.5)]),
    "heard": footage([("s-heard.mp4", 8)]),
    "repro": footage([("s-repro.mp4", 8)]),
    "conditions": card('<p class="kicker">Real conditions, not role-play</p><div class="cols">'
                       '<div class="col c0"><b>Slow 3G phone</b><span>+3 s on every request</span><span>360 px screen</span></div>'
                       '<div class="col c1"><b>Hindi user</b><span>Browser locale hi-IN</span><span>Hindi page, Hindi errors expected</span></div>'
                       '<div class="col c2"><b>Screen-reader user</b><span>Sees only the accessibility tree</span><span>Unnamed buttons can\'t be used</span></div></div>',
                       [(".kicker", 0.2), (".c0", 1), (".c1", 2), (".c2", 3)]),
    "evidence": card('<p class="kicker">The rule</p><h2 class="mid">No evidence, no verdict.</h2>'
                     '<p class="lede">Code watching the browser collects it. The model can only cite it.</p><ul class="chips">'
                     + "".join(f'<li class="chip h{i}">{E(e)}</li>' for i, e in enumerate(EVIDENCE)) + '</ul>',
                     [(".kicker", 0.2), (".mid", 0.4), (".lede", 1)] + [(f".h{i}", (2, 2.2 + i * 1.5)) for i in range(7)]),
    "fix": shots([("shot-tavily.png", "Case detail: sources Tavily found before the fix", 1),
                  ("shot-double.png", "Case detail: evidence, the fix and its diff", 1.3)]),
    "guard": footage([("s-fixed.mp4", 5), ("s-detail.mp4", 16.5)]),
    "users": card('<p class="kicker">Seven planted bugs, seven kinds of user</p><ul class="users">' + rows(USERS) + '</ul>',
                  [(".kicker", 0.2)] + [(f".r{i}", i + 1) for i in range(7)]),
    "grouping": card('<p class="kicker">One bug, many complaints</p><div class="flow">'
                     '<div class="bubbles g0"><p>"otp nahi aa raha, baar baar something went wrong"</p><p>"never got the login code"</p><p>"code hi nahi aaya yaar"</p></div>'
                     '<div class="box g1"><b>Nemotron Embed</b><span>finds the 3 nearest open cases</span></div>'
                     '<div class="box g2"><b>Nemotron 3.5 Lightning</b><span>"Same problem?"</span></div>'
                     '<div class="box g3"><b class="badge">×3 reports</b><span>one investigation</span></div></div>'
                     '<p class="stat-line g4"><b>0.82</b> precision on held-out complaints: right about 4 times in 5 when it merges</p>',
                     [(".kicker", 0.2), (".g0", 0), (".g1", 1), (".g2", 2), (".g3", 3), (".g4", 4)]),
    "results": card('<p class="kicker">7 planted bugs · 3 full runs each</p><div class="stats">'
                    '<div class="stat ok s0"><p class="n">21/21</p><p class="l">reproduced</p></div>'
                    '<div class="stat ok s1"><p class="n">20/21</p><p class="l">fixed and proven</p></div>'
                    '<div class="stat ok s2"><p class="n">20/21</p><p class="l">guarded by a test</p></div>'
                    '<div class="stat s3"><p class="n">0</p><p class="l">false alarms</p></div></div>'
                    '<p class="lede miss">The one miss stopped at "fix failed" instead of shipping a guess.</p>',
                    [(".kicker", 0.2), (".s0", 2), (".s1", 3), (".s2", 4), (".s3", 5), (".miss", 6)]),
    "stack": card('<p class="kicker">Under the hood</p><ul class="users">' + rows(STACK) + '</ul>',
                  [(".kicker", 0.2)] + [(f".r{i}", i) for i in range(5)]),
    "limits": card('<p class="kicker">Limits, honestly</p><ul class="users">'
                   + rows([("Web apps only", "not native mobile apps"), ("Small, local fixes", "a timeout, a label, a CSS rule"),
                           ("Seven planted bugs", "a working demonstration, not a broad benchmark")])
                   + '</ul><div class="todo t3"><b>Before submitting</b><span>Nebius Token Factory key (required by the rules) · final video under 3:00</span></div>',
                   [(".kicker", 0.2), (".r0", 0), (".r1", 1), (".r2", 2), (".t3", 3)]),
    "close": card('<p class="quote">Your angriest users are your best testers.</p>'
                  '<p class="link">github.com/yashasviyadav30/complaint-replay</p><p class="lede">Built solo by Yashasvi Yadav.</p>',
                  [(".quote", 0.2), (".link", 1), (".lede", 2)]),
}


def build() -> str:
    narration = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
    body, subs, audio, anims, t = [], [], [], [], 0.0
    for i, scene in enumerate(narration):
        sid = scene["id"]
        voice = length(HERE / "assets" / "vo" / f"{sid}.wav")
        dur = LEAD + voice + TAIL
        st = sentence_starts(scene["text"], t + LEAD, voice)
        visual, a = SCENES[sid](sid, t, dur, st)
        body.append(f"<!-- {sid} {t:.1f}-{t + dur:.1f} -->\n{visual}")
        anims += a
        audio.append(f'<audio id="vo-{sid}" src="assets/vo/{sid}.wav" data-start="{t + LEAD:.2f}" '
                     f'data-duration="{voice:.2f}" data-track-index="{5 + i % 2}"></audio>')
        for j, (text, s0, d) in enumerate(timed(scene["text"], t + LEAD, voice)):
            subs.append(f'<p id="sub-{sid}-{j}" class="clip sub" data-start="{s0:.2f}" data-duration="{d:.2f}" data-track-index="1">{E(text)}</p>')
        t += dur
    js = []
    for a in anims:
        if a[0].startswith("push:"):
            js.append(f'tl.fromTo("{a[0][5:]}", {{ scale: 1 }}, {{ scale: 1.04, duration: {a[2]:.2f}, ease: "none" }}, {a[1]:.2f});')
        else:
            js.append(f'rise("{a[0]}", {a[1]:.2f});')
    template = (HERE / "template.html.in").read_text(encoding="utf-8")
    return (template.replace("{{DURATION}}", f"{t:.2f}")
            .replace("{{BODY}}", "\n".join(body + subs + audio))
            .replace("{{ANIMS}}", "\n      ".join(js)))


if __name__ == "__main__":
    (HERE / "index.html").write_text(build(), encoding="utf-8")
    print("wrote index.html")
