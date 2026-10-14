# Complaint Replay

**Your users already told you what's broken. Complaint Replay proves it, fixes it, and makes sure it never comes back.**

A customer writes *"OTP never comes!"*. The developer tries it on a fast laptop, it works, and the complaint is closed as "can't reproduce". Studies of real bug trackers put that at 13-24% of all bug reports ([ICSME 2020](https://marco-c.github.io/publications/non_reproducibility-icsme2020.pdf)), and a large share fail because the user's device, network or settings differ from the developer's.

Complaint Replay closes that gap:

1. **Hears** the complaint: typed into a one-line "Report a problem" widget, or a silent signal (rage clicks, page errors, failed or very slow requests). The widget also records the user's real conditions: network, screen size, language, device.
2. **Reproduces** it: an AI twin opens a real browser **under those exact conditions** and repeats what the user did, step by step.
3. **Proves** it with machine evidence only. The AI is not allowed to say "reproduced" on its own word.
4. **Fixes** it: NVIDIA Nemotron reads the evidence and the code and writes the smallest fix, on a separate branch copy.
5. **Proves the fix**: the same twin replays the complaint on the fixed code.
6. **Guards** it: the steps that triggered the bug become a test that must pass on the fix and fail on the old code.

Built for the Nebius x NVIDIA Global AI Hackathon (Coding and Agentic Engineering track).

- **Recorded demo (real cases, read-only):** https://yashasviyadav30.github.io/complaint-replay/
- **Demo video:** recorded from one real, unscripted run; see `video/README.md` for exactly how it was cut.

## Results

Five realistic bugs planted in a demo store, each tied to a different kind of user. Every bug was run through the whole chain three times, and each complaint was also replayed on the clean store to check for false alarms. Measured on Oct 12, 2026 with `uv run python bench.py 3`.

| Bug | User condition | Reproduced | Fixed + proven | Guarded | False alarm on clean shop | Median time |
|---|---|---|---|---|---|---|
| OTP request gives up after 4 seconds | Slow 3G + cheap Android | 3/3 | 3/3 | 3/3 | no | 76 s |
| Pay button pushed off-screen on small phones | Slow 3G + cheap Android | 3/3 | 3/3 | 3/3 | no | 156 s |
| Wrong-OTP error shown only in English | Hindi speaker | 3/3 | 3/3 | 3/3 | no | 39 s |
| Cart button has no accessible name | Screen-reader user | 3/3 | 3/3 | 3/3 | no | 58 s |
| Coupon shown in cart but not applied at payment | Fast desktop | 3/3 | 3/3 | 2/3 | no | 66 s |

**Total: 15/15 reproduced, 15/15 fixed and proven, 14/15 guarded, 0 false alarms.**

Be clear about what this does and does not show. These are five bugs we planted ourselves, so it is a working demonstration, not a broad benchmark. The OTP bug, for example, never shows up on a fast laptop, which is exactly the "works for me" trap: the scripted test `test_otp_bug_works_for_me_on_a_fast_laptop` checks that.

## Duplicate complaints: one bug, one investigation

Forty people describe one bug forty ways ("otp nahi aa raha", "never got the code"). A new complaint is embedded
with **NVIDIA Nemotron Embed** (`nemotron-3-embed-1b`); the 3 most similar open cases are each checked by
**Nemotron 3.5 Lightning** ("same problem?"), and on a yes it joins that case instead of starting another
investigation. The board then sorts by how many people a bug hurts ("x12 reports").

The settings were tuned, not guessed: `scripts/calibrate_grouping.py` replays 57 hand-written complaints
(English, Hinglish, Hindi; `data/complaints_labeled.json`) in arrival order, picks the setting on one half and
measures it on the other half:

| Held-out half | Precision | Recall | F1 |
|---|---|---|---|
| Embedding similarity alone | 0.61 | 0.71 | 0.65 |
| Top-3 nearest cases + Nemotron check (in use) | 0.82 | 0.58 | 0.68 |

Read this plainly: when it merges, it is right about 4 times in 5; it would rather miss a duplicate (an extra
investigation) than merge two different bugs (hiding one). The test set is small (27 complaints), so treat the
numbers as a first measurement, not a benchmark. Every merged report stays visible in the case for a human to check.

## How NVIDIA Nemotron and Nebius are used

| Job | Model | Why this one |
|---|---|---|
| Navigator: picks one click or keystroke at a time | Nemotron 3 Super (thinking off) | Fast and cheap per step; thinking adds nothing to "click Pay" |
| Judge: does this machine evidence match the complaint? | Nemotron 3 Super (thinking off) | A narrow yes/no question, kept separate from navigation |
| Fixer: reads evidence + source, writes the patch | Nemotron 3 Super (reasoning on) | Root-cause reasoning is where thinking pays off |
| Research: finds the documented cause of the evidence before the fix | Tavily search API | The fix can cite a real source (for example the axe rule page) instead of guessing |

All model calls go through one OpenAI-compatible client (`replay/llm.py`). With `NEBIUS_API_KEY` set it calls **Nebius Token Factory**; with only `NVIDIA_API_KEY` it calls NVIDIA's API catalog. The results table above was measured on NVIDIA's API catalog endpoint with the same Nemotron 3 Super model. A hard token budget per run (`REPLAY_TOKEN_BUDGET`) stops a looping agent from running up a bill.

Things we learned the hard way, so you don't have to:

- With thinking on, Nemotron sometimes used its whole token budget thinking and returned an empty answer. Browser steps now run with `enable_thinking: False`.
- One model doing both navigation and judging tended to wander after the bug had already shown. Splitting out a small judge, which runs only when new evidence appears, fixed that.

## The rules that make it trustworthy

- **Real conditions, not role-play.** The twin doesn't pretend to be on a slow phone. The browser really adds 3 s per request, really has a 360 px screen, really runs in Hindi. The screen-reader twin sees only the accessibility tree.
- **No evidence, no verdict.** Evidence is collected by code watching the browser: failed requests, HTTP errors, console errors, controls off screen, English-only errors shown to Hindi users, axe-core accessibility violations, money values that disagree between API calls. The model can only cite evidence ids; a "reproduced" verdict without real evidence is downgraded.
- **Unreadable model replies never decide anything.** They become a short wait, and the next step tries again.
- **Fixes never touch the live app.** They go to a branch copy, the way a pull request would.
- **Privacy.** The widget never sends what users type into fields, only button names. Phone numbers, emails and long ID numbers in complaints are masked before storage or any model call.

## Run it

Needs Python 3.13, [uv](https://docs.astral.sh/uv/), Node 22.

```bash
uv sync
uv run playwright install chromium
cd dashboard && npm install && npm run build && cd ..
cp .env.example .env        # add NEBIUS_API_KEY (Token Factory)
uv run uvicorn server.app:app --port 8200
```

Open http://127.0.0.1:8200 for the dashboard. The demo store runs at http://127.0.0.1:8100 with the widget in the corner.

1. Press **Break It** to plant a random secret bug.
2. Use the store like a customer. When something goes wrong, press **Report a problem** and complain in your own words, or just rage-click.
3. Watch the case move across the board: Heard, Reproduced, Fixed, Guarded.

Other entry points:

```bash
uv run pytest -q                   # 23 tests; scripted browser checks need no API key
uv run python pipeline.py 4        # one planted bug, end to end, from the command line
uv run python bench.py 3           # the results table above
uv run python -m replay.guard <branch>/guards/<id>.json http://127.0.0.1:8100   # run one guard
```

## Project layout

| Path | What it is |
|---|---|
| `server/` | The service: complaint API (validation, PII masking, rate limit), live demo store, investigations, `widget.js` |
| `replay/` | The engine: conditions, browser + evidence, navigator + judge, fixer, guard |
| `badshop/` | The demo store, bug-free; bugs are injected into a copy |
| `dashboard/` | The case board (React, Vite, Tailwind) |
| `tests/` | Unit tests and real-browser scripted tests |

## Limits, honestly

- Web apps only (desktop and mobile web). Native mobile apps would need emulators.
- Fixing works best on small, local bugs: a timeout, a label, a CSS rule, a wrong variable. Larger refactors are out of scope.
- Fixing needs access to the code. Without it you still get the reproduction, the evidence and the guard steps.
- One investigation runs at a time, because each drives a real browser.

## License

Apache 2.0. See [LICENSE](LICENSE).
