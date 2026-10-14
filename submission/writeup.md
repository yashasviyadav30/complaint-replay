# Devpost write-up

> Do not paste until the Token Factory blocker in `checklist.md` is resolved. Every sentence below must be
> true on the day you submit.

**Project name:** Complaint Replay (working name)

**Tagline (under 60 characters):** Your users' complaints, reproduced, fixed and guarded.

**Track:** Coding and Agentic Engineering

**Built with:** nvidia-nemotron, nebius-token-factory, python, fastapi, playwright, react, vite, tailwindcss, axe-core

---

## Inspiration

A customer writes "OTP never comes!". The developer tries it on a fast laptop with good Wi-Fi. It works, so the complaint is closed as "can't reproduce" and the customer leaves.

That is not rare. Studies of real bug trackers find 13-24% of bug reports are never reproduced, and a large share fail because the user's device, network or settings differ from the developer's. Small teams feel this most: no QA team, no device lab, and a support inbox full of complaints nobody can prove.

## What it does

Complaint Replay turns a user's complaint into proof of the bug, a fix and a test. An AI twin replays the complaint in a real browser under that user's real conditions (slow network, small phone screen, Hindi, screen reader), proves the bug with machine evidence, has NVIDIA Nemotron write the fix, and saves the steps that triggered it as a test so the bug can't silently come back.

How a case moves:

1. **Heard.** A one-line widget adds a "Report a problem" button to any site. It also catches silent frustration: rage clicks, page errors, failed or very slow requests. With each complaint it records the user's real conditions, never what they typed into fields.
2. **Reproduced.** The twin opens a real browser with those exact conditions and repeats what the user did. Evidence is collected by code watching the browser, not by the model: failed requests, controls pushed off screen, English-only errors shown to a Hindi user, accessibility violations, a cart total that disagrees with the amount charged.
3. **Fixed.** Nemotron reads the evidence and the code and writes the smallest fix, on a separate branch copy. The same twin replays the complaint on the fixed code.
4. **Guarded.** The steps that triggered the bug become a test. It must pass on the fix and fail on the old code, or it isn't marked guarded.

On seven realistic bugs (slow phone, small screen, Hindi user, screen reader, elderly user with large text, double charge, coupon charge), each run three times: 21/21 reproduced, 20/21 fixed and proven, 20/21 guarded, and 0 false alarms when the same complaints were replayed on the clean store.

## How we built it

- **NVIDIA Nemotron 3 Super on Nebius Token Factory**, in three roles. The navigator picks one click or keystroke at a time with thinking off, because "click Pay" needs speed, not reasoning. A separate judge answers one narrow question whenever the browser records new evidence: does this match the complaint? The fixer runs with reasoning on, because root-cause analysis is where thinking pays off.
- **Playwright** drives real Chromium. Conditions are enforced, not role-played: 3 seconds of added latency per request, a 360 px phone screen, a Hindi locale, or an accessibility-tree-only view for the screen-reader twin.
- **axe-core** gives hard accessibility evidence.
- **NVIDIA Nemotron Embed** groups duplicate complaints (in any language) so one bug gets one investigation and a count of how many people it hurts; a Nemotron check confirms each merge. Settings were tuned on a labelled set and measured on a held-out half (precision 0.82).
- **FastAPI** runs the complaint service: input validation, PII masking (phones, emails, long ID numbers), rate limiting, the live demo store and background investigations.
- **React, Vite and Tailwind** for the case board: Heard, Reproduced, Fixed, Guarded, with screenshots, evidence, the diff, the proof and the guard for each case.
- A hard token budget per run stops a looping agent from running up a bill.

## Challenges we ran into

**The bug that only happened half the time.** Our first slow-phone profile slowed the CPU 4x as well as the network. The OTP timeout bug then reproduced only some of the time, which is useless for proof. We traced it to Chrome's CPU throttling firing page timers late, so a 4-second timeout sometimes waited 6. Removing CPU throttling made the bug reproduce every time on a slow connection and never on a fast laptop, which is exactly the "works for me" trap we wanted to show. A test now checks both sides.

**Empty answers from a thinking model.** In the first full run, every reply was empty. The model spent its whole token budget thinking and never wrote the answer. Turning thinking off for single browser steps fixed it and cut tokens per step roughly 16x; we kept reasoning on only for the fixer.

**An AI that kept poking after it had already found the bug.** One model doing both navigation and judging would see "Pay button is off screen" and keep clicking for 20 steps. Splitting out a small judge that runs only when new evidence appears took us from 1 of 5 reproductions to 4 of 5 in the next test run, and fixing the timer issue above got all five.

## Accomplishments that we're proud of

- The full chain runs on its own, from a complaint typed in the widget to a guarded fix, with no human step in between.
- The model can't fake a result. A "reproduced" verdict without real browser evidence is downgraded, and an unreadable model reply can never decide anything.
- The guard is checked both ways: it passes on the fix and fails on the old code, so it really catches the bug if it returns.

## What we learned

- Simulate conditions, don't role-play them. A model told "you are on a slow phone" finds nothing; a browser that really is slow finds the bug.
- Separate the agent that acts from the agent that judges. Each gets simpler and more reliable.
- Decide success with evidence, not with the model's opinion of its own work.

## What's next

1. Open pull requests directly through a GitHub App, so a fix lands in the team's normal review flow.
2. Pull public complaints (app reviews, forums) into the same pipeline.
3. A patrol mode that tests key flows every night under the conditions real complainers had.

## Try it

- Repo: https://github.com/yashasviyadav30/complaint-replay
- Recorded demo (real cases, read-only): https://yashasviyadav30.github.io/complaint-replay/
- Run it live: five commands in the README.
