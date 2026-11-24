---
name: complaint-replay
description: Reproduce a web app bug report in a real browser as the user who wrote it (their phone, slow or patchy network, language, screen reader, keyboard only, 200% zoom), prove it with evidence the browser recorded, fix it, and save a guard test that fails if the bug comes back. Use when a user's bug "can't be reproduced" or "works for me", when a report mentions a phone, iPhone, slow internet, another language, a screen reader, a keyboard, large text or a double charge, or before closing any user bug report.
summary: Replay a user's bug report in a real browser as that user, prove it with browser evidence, fix it and keep a guard test.
version: 1.0.0
tags: [debugging, bug-reproduction, browser-testing, accessibility, playwright, mcp, regression-testing, mobile-web]
keywords: [can't reproduce, works for me, bug report, slow 3g, screen reader, keyboard only, rtl, double charge, guard test]
use_cases:
  - Reproduce a "can't reproduce" bug report on the user's own device and network
  - Check a page as a screen-reader or keyboard-only user
  - Catch a payment that is charged twice when the signal drops
  - Keep a regression test made from the user's exact steps
docs_url: https://github.com/yashasviyadav30/complaint-replay#readme
---

# Complaint Replay

Developers test on a fast laptop. Users hit bugs on a cheap Android phone on 3G, in Arabic, with a screen reader, or
at 200% zoom. With this skill you replay the complaint as that user in a real browser, instead of guessing.

The `complaint-replay` MCP server does the replay. Its tools:

| Tool | What it does |
|---|---|
| `replay_complaint(complaint, user, device, network, url, fix)` | Drives Chromium or WebKit as the user. Returns the verdict, the evidence and the path of the case file |
| `run_guards(url)` | Replays the saved steps of every bug fixed before. FAIL means a user's bug is back |
| `find_devices(name)` | Searches the 207 device profiles, e.g. `galaxy`, `iphone 15`, `pixel` |

## Setup (once)

If those tools are missing, ask the user to run these from the web app's repo:

```bash
uv tool install "complaint-replay[mcp] @ git+https://github.com/yashasviyadav30/complaint-replay"
crp setup                                    # downloads the Chromium and WebKit browser engines
crp init                                     # writes complaint-replay.toml and a GitHub workflow
claude mcp add complaint-replay -- crp mcp   # Cursor and other MCP clients use the same command: crp mcp
```

Then check two things with them:

- **A model key** in the environment: `NVIDIA_API_KEY` (free at build.nvidia.com), or `NEBIUS_API_KEY`, or
  `REPLAY_BASE_URL` and `REPLAY_API_KEY` for any OpenAI-compatible server (vLLM, NVIDIA NIM, Ollama).
- **`complaint-replay.toml`** at the repo root. `start` is how to start the app, with `{port}` where the port goes
  (e.g. `npm run dev -- --port {port}`). `edit` lists the files a fix may change. `hints` holds what a new user
  would need to know, such as a test login. A fix always needs `start`, even when you replay a `url`.

**What leaves the machine:** the replay sends the complaint, what the browser sees on each page and short excerpts
of the app's source code to the model provider the user configured. The browser loads only the app under test.
Nothing goes anywhere else. Tell the user this before the first replay of a private app.

## When to use it

- A user report says "doesn't work", "button missing", "stuck loading", "charged twice" or "can't find", and you
  can't see the bug yourself.
- The report mentions a device, a slow or patchy connection, a language, a screen reader, a keyboard, large text,
  dark mode or an older person using the app.
- Before you close a user report as "can't reproduce" or "works for me".
- After you change code on a page a user complained about: call `run_guards`.

Not for backend-only bugs with no web page, native mobile apps or load testing.

## Workflow

### 1. Pick the user

Match the report to a ready-made `user`, or to a `device` and `network`:

| The report says | `user` | or `device` + `network` |
|---|---|---|
| phone, Android, cheap phone, slow | `slow_3g_android` | `find_devices("galaxy")`, `slow-3g` |
| iPhone, iPad, Safari | `iphone` (runs in WebKit, Safari's engine) | `find_devices("iphone")` |
| blind, screen reader, VoiceOver, NVDA, TalkBack | `screen_reader` | |
| no mouse, Tab key, keyboard | `keyboard` | |
| my mother, older, big text, zoom, "too fast" | `elderly` | |
| written in Hindi or Arabic, phone set to it | `hindi`, `arabic` | |
| on a train, signal dropped, paid twice | `train` | `tunnel` |
| patchy data, random failures | `flaky_network` | `flaky` |
| control case: does it work for a developer? | `fast_desktop` | |

Networks: `wifi`, `4g`, `3g`, `slow-3g`, `2g`, `satellite`, `flaky`, `tunnel`, `drops`.
Pass the complaint in the user's own words and language. Do not rewrite it into developer terms. The replay reads
needs the user states ("I use a screen reader", "मुझे बड़े अक्षर चाहिए") and applies them.

### 2. Replay

Call `replay_complaint(complaint, user=..., fix=true)`. It reproduces first and only tries a fix if the bug is
proven. Use `fix=false` when the user only wants to know whether the bug is real. A replay takes a few minutes and
a fix several more. Only one runs at a time, so tell the user it is running.

`url` replays a site that is already running. Leave it empty to start the app from `complaint-replay.toml`.

### 3. Read the result

The result has a `Verdict:` line, a summary, then evidence lines like
` * E3 [offscreen_control] 'Pay now' is outside the screen (left=402px, screen=360px)`.
Lines marked `*` are the proof the verdict cites. Every evidence line comes from code watching the browser, not
from a model. Quote the `*` lines to the user. [reference/evidence.md](reference/evidence.md) explains each kind.

| Verdict | Meaning | What you do |
|---|---|---|
| `guarded` | Reproduced, fixed, proven, and the guard fails on the old code | Step 4 |
| `fixed` | Reproduced and fixed, but the guard does not fail on the old code | Step 4, and tell the user the guard is weak |
| `fix_failed`, `fix_unproven` | Bug proven, but the automatic fix did not apply or did not hold | Step 5 |
| `reproduced` | Bug proven (you ran with `fix=false`) | Fix it yourself, or run again with `fix=true` to get a guard |
| `ux_confusion` | Nothing is broken, but this user gets lost | Explain where from the summary and suggest a clearer UI. Change nothing on your own |
| `not_reproduced` | The user's task finished without the problem | Say so plainly. Try one other likely user or network, then stop |

Never state a cause that no evidence line shows. A verdict without a `*` line has already been downgraded to
`not_reproduced`.

### 4. Bring the fix and the guard into the repo

The fix is made in a temporary copy of the repo, not in the user's working tree. The result prints its diff after
`Fix:`. The guard, saved as `.complaint-replay/guards/<case id>.json`, also lives only in that copy.

1. Apply the printed diff to the user's working tree, or make the same edit by hand.
2. Open the case file (the path on the `Case file:` line, `.complaint-replay/runs/<case id>.json`). Write the JSON
   value of its `guard.test` field, unchanged, to `.complaint-replay/guards/<case id>.json`.
3. Call `run_guards`. Every guard must pass.

### 5. When the automatic fix failed

The bug is still proven, and the case file still holds `guard.test`, so save the guard as in step 4.2. Then fix the
code yourself. Use the `*` evidence, the case file's `replay.steps` and the files named under `fix`, which the fixer
read or tried. Call `run_guards` after each change until every guard passes. The new guard is the acceptance test.

### 6. Report

Tell the user:

- the verdict and the `*` evidence lines
- what you changed (a small diff, in the file the evidence points to)
- the `run_guards` result
- the case file path. Next to it, `.complaint-replay/runs/shots/` holds `<case id>-before.gif` and, after a fix,
  `<case id>-after.gif`: captioned films of the steps, worth adding to the pull request

## Rules

- Never edit or delete a file in `.complaint-replay/guards` to make a run pass. A failing guard means a real user's
  bug is back: fix the code.
- Never say a bug is fixed until `run_guards` passed after your change.
- Never put real passwords, card numbers or personal data in the complaint. For pages behind a login, ask the user to
  run `crp auth --url <site>` once and add the `auth` line it prints to `complaint-replay.toml`. Keep that file out
  of git.
- Keep `.complaint-replay/runs/` out of git. It holds screenshots and page text. Commit the guards.
- Fixes stay local. Commit, push or open a pull request only when the user asks.

## Example

The user says: "Issue #42: 'I added everything to my cart but there is no button to pay.' Sent from a Galaxy phone."

1. `find_devices("galaxy")` → `Galaxy S9+` is listed.
2. `replay_complaint("I added everything to my cart but there is no button to pay", device="Galaxy S9+", network="slow-3g", fix=true)`
3. Result: `Verdict: guarded`, proof ` * E2 [offscreen_control] 'Pay now' is outside the screen (left=402px, screen=360px)`,
   and a one-line CSS diff in `src/Cart.css`.
4. Apply the diff, save the guard from the case file, then `run_guards` → `3/3 guards pass`.
5. Reply with the evidence line, the diff, the guard result and the two films.
