# Agensi listing: Complaint Replay

Paste these into the form at agensi.io/dashboard/submit. Not part of the ZIP.

## Name (max 60)

Complaint Replay: reproduce bug reports as the real user

## Summary (max 300)

Your agent replays a user's bug report in a real browser as that user: their phone, slow network, language, screen reader or keyboard. It proves the bug with evidence the browser recorded, fixes it, and saves a guard test that fails if the bug ever comes back.

## Description

"Works on my machine" is where many real bug reports go to die. The user was on a cheap Android phone on 3G, or had
the phone set to Arabic, or used a screen reader. The developer tests on a fast laptop and closes the issue.

This skill teaches your coding agent to replay the complaint as that user instead of guessing. It uses the open-source
Complaint Replay MCP server, which drives a real Chromium or WebKit browser with the user's device (207 profiles),
network (3G, flaky, signal drops mid-payment), language, timezone, zoom and input method.

**What your agent does with it**

- Maps the report to the right user: slow Android, iPhone in Safari's engine, screen reader, keyboard only, older
  user at 200% zoom, Hindi, Arabic, a train with a dropping signal
- Replays it and reads the evidence: code watching the browser records failed requests, controls off screen,
  buttons announced only as "1", text in the wrong language, the same payment sent twice. The model can cite
  evidence but cannot invent it, and a verdict with no evidence is downgraded to "not reproduced"
- Fixes the bug in a copy of the repo, replays the same steps on the fix, and keeps them as a guard test
- Runs every guard after later changes, so an old user's bug can't quietly come back
- Reports the evidence, the diff, the guard result and two captioned films (the bug, then the fix)

**What's in the skill:** when to reach for a replay, how to pick the user from the report's wording, how to read
each verdict and evidence kind, how to bring the fix and guard into your repo, and rules the agent must keep (never
edit a guard to make it pass, never claim a fix before the guards pass, never put real personal data in a replay).

## See it in action

Request: "Issue #42 says: 'I added everything to my cart but there is no button to pay.' The user is on a Galaxy
phone. Can you check it?"

The agent looks up the device with `find_devices("galaxy")` and calls `replay_complaint` with the complaint in the
user's words, `device="Galaxy S9+"`, `network="slow-3g"` and `fix=true`. A real browser opens at 360 px wide on a
slow connection, maps the shop's screens, adds items to the cart and goes to checkout, one action at a time.

Result: `Verdict: guarded`. The proof line reads `[offscreen_control] 'Pay now' is outside the screen`. That line
was recorded by the browser, not written by the model. The fixer changes the cart layout so the button fits on
narrow screens. It then replays the exact same steps on the patched code with no model involved, and the button is
on screen. The same steps run on the old code still fail, so they become a guard test.

The agent applies the diff to the working tree, saves the guard to `.complaint-replay/guards/`, runs every guard
(all pass), and replies with the evidence line, the one-file diff and two GIFs: the user's phone without a Pay
button, then the same steps with it.

## Compatibility note

Requires Python 3.13 and uv, plus a free NVIDIA API key (build.nvidia.com), a Nebius key, or any OpenAI-compatible
model server. Web apps only. Works with any agent that supports MCP servers.

## Categories (pick up to 3; first one sets the main page)

Testing / QA, Debugging, Accessibility. Use the closest names in Agensi's list.

## Tags

debugging, bug reproduction, browser testing, accessibility, playwright, mcp, regression testing, mobile web, qa

## Use cases

- Reproduce a "can't reproduce" bug report on the user's own device and network
- Check a page as a screen-reader or keyboard-only user
- Catch a payment charged twice when the signal drops
- Turn a user's exact steps into a regression test

## Permissions

- Terminal: yes. The user installs the MCP server once with uv, and the server starts the app under test.
- Read files: yes, the app's source, to fix it.
- Write files: yes. The agent applies the fix and saves guard tests to `.complaint-replay/guards/`.
- Browser: yes, a local headless Chromium or WebKit.
- Network: yes, to the model provider the user configures, and to the app under test.
- Environment variables: the model key (`NVIDIA_API_KEY`, `NEBIUS_API_KEY` or `REPLAY_API_KEY`), read by the MCP
  server only.

## Limitations

- Web apps only. Native mobile apps would need emulators.
- Automatic fixes work best on small, local bugs: a label, a CSS rule, a timeout, a wrong variable. When a fix
  fails, the proven guard still becomes the acceptance test for the agent's own fix.
- A replay takes a few minutes, and only one runs at a time.
- On a benchmark of 8 real bugs from Actual Budget, the full loop solved 1 of 8. Reproduction works far more often
  than fully automatic fixing, so the skill has the agent finish the fix when the automatic one fails.

## FAQ

**Is the tool free?** Yes. The MCP server is open source (Apache 2.0) and runs on NVIDIA's free API catalog.

**Does my code leave my machine?** Only short source excerpts, sent to the model provider you choose. Point it at
your own model server (vLLM, NIM, Ollama) and nothing leaves at all.

**Does it open pull requests by itself?** No. The skill keeps fixes local until you ask.

## Docs link

https://github.com/yashasviyadav30/complaint-replay#readme

## Video

https://youtu.be/cWFVZ0VkMG4

## Screenshots

`docs/media/pay-button-before.gif` and `docs/media/pay-button-after.gif` from the repo.

## Price

Free (recommended to start). Paid needs a payout method and a Stripe identity check.
