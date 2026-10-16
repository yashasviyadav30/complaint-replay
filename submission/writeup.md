# Devpost write-up

> Do not paste until the Token Factory blocker in `checklist.md` is resolved and every `[FILL]` below is
> replaced with a measured number. Every sentence must be true on the day you submit.

**Project name:** Complaint Replay (working name; final name due Oct 18)

**Tagline (under 60 characters):** Your users' complaints, reproduced, fixed and guarded.

**Track:** Coding and Agentic Engineering

**Built with:** nvidia-nemotron, nebius-token-factory, tavily, python, fastapi, playwright, github-actions, react, vite, tailwindcss, axe-core, fasttext

---

## Inspiration

A customer writes "OTP never comes!", or "الزر لا يعمل", or "I use a screen reader and can't find the cart". The developer tries it on a fast laptop with good Wi-Fi. It works, so the complaint is closed as "can't reproduce" and the customer leaves.

That is not rare. Studies of real bug trackers find 13-24% of bug reports are never reproduced, and a large share fail because the user's device, network or settings differ from the developer's. Small teams feel this most: no QA team, no device lab, and a support inbox full of complaints in languages nobody on the team reads.

## What it does

Complaint Replay turns a user's complaint into a pull request: proof of the bug, the fix, and a test that stops it from coming back.

1. **Hears.** A one-line widget adds "Report a problem" to any site, in 17 languages. With each complaint it records the user's real conditions: screen, device, network, language, timezone, dark mode, reduced motion. It also catches silent frustration (rage clicks, page errors, failed requests), and takes complaints from GitHub issues, support-desk email and Sentry.
2. **Reproduces.** In the team's own GitHub Actions, an AI twin opens a real browser under those exact conditions and repeats what the user did. If the user says they use a screen reader or only a keyboard, in any language, the twin does too.
3. **Proves.** Evidence comes only from code watching the browser: failed requests, a button pushed off a phone screen, an English error shown to a Hindi user, a control a screen reader announces only as "1", the same payment sent twice. The model may cite evidence; it cannot invent it.
4. **Fixes.** NVIDIA Nemotron reads the evidence, web research about it, and the relevant source files, and writes the smallest fix on a new branch.
5. **Guards.** The steps that triggered the bug run again on the fix, by code, with no model. They become a test that must pass on the fix and fail on the old code, and it runs in CI on every later pull request.
6. **Closes the loop.** A pull request arrives with the evidence, before/after screenshots and the guard. The person who complained sees "fixed" in the widget.

The source code never leaves the team's CI. Teams set it up in about ten minutes: one script tag, one workflow file, one GitHub App click.

## How we built it

- **NVIDIA Nemotron 3 Super on Nebius Token Factory**, in four roles with different settings. The navigator picks one click or keystroke at a time with thinking off, because "tap Pay" needs speed. A judge, plus a second skeptic question per item, decides whether each piece of evidence shows the problem the user described. A reader picks out what users say about themselves ("I'm blind", "मुझे बड़े अक्षर चाहिए"). The fixer reads evidence and code with reasoning on.
- **Nemotron Embed** groups the same bug reported in different languages, so one bug gets one investigation and a count of how many people it hurts.
- **Playwright** drives real Chromium. Conditions are enforced, not role-played: 207 device profiles, eight network profiles from 4G to "drops after load", locale and timezone, right-to-left, forced colors, 200% text, an accessibility-tree-only view for the screen-reader twin, Tab-only for the keyboard twin.
- **axe-core** and **fastText language ID** give hard accessibility and language evidence on CPU.
- **Tavily** searches for the documented cause of the evidence before the fix; the pull request lists the sources the fix relied on.
- **GitHub Actions** runs every replay in the customer's own CI. A **FastAPI** server handles projects, widget keys, PII masking (including Devanagari digits, PAN and Aadhaar), signed case tokens, retention and a GitHub App made from a manifest in one click. **React, Vite and Tailwind** for the dashboard: setup wizard, an impact-ranked board, case detail with evidence, diff, proof and guard.
- Self-host with Docker Compose, or bring your own model through any OpenAI-compatible server.

## Results, misses included

- **On someone else's code:** a public React shopping cart we did not write, copied unchanged. Three real accessibility bugs, three complaints, three guarded pull requests, one of them through the full loop from widget to pull request to "fixed" in the widget. A fourth complaint, written in Hindi, was also fixed and guarded.
- **On real bugs from a real product:** 8 bugs that the developers of Actual Budget (an open-source budgeting app) fixed in the last two months. We put each bug back by reversing the real fix, gave Complaint Replay only a user-style complaint, and counted it solved only if it fixed the bug in the same file the real developers changed. Result: **[FILL] of 8**. Full table, every miss included: `benchmarks/real-bugs.md`.
- **On planted bugs:** 7 bugs, 3 runs each: 21/21 reproduced, 20/21 fixed and guarded, 0 false alarms on the clean app.
- **Languages:** on 400 complaints in 20 languages written by Nemotron (synthetic, said plainly), the same bug in another language is matched 97% of the time, and triage is 98% right on held-out data.

## Challenges we ran into

**The bug that only happened half the time.** Our first slow-phone profile slowed the CPU as well as the network. A timeout bug then reproduced only some of the time, which is useless as proof. Chrome's CPU throttling fired page timers late. Without it, the bug reproduced every time on a slow connection and never on a fast one.

**A real app is not a demo app.** On Actual Budget the first pass solved 0 of 8. The twin wandered while the app was still loading, pressed the same button nine times without noticing, and once "proved" a bug with an unrelated obstacle on the way. Each miss became a fix: wait until the app says it is ready, show the twin what each past tap hit, ask a second skeptic question for every piece of evidence, and refresh a page that never finishes loading. [FILL: the before/after numbers.]

**The fixer looked in the wrong file.** In a big repo the fixer only sees some files. For a date picker that would not open on Android, it read the transaction list, while the real bug sat in a shared input component one import away. Evidence now names the element (`<input type="date">`), and the file picker follows imports, including path aliases.

**A free endpoint under load.** Three benchmark jobs sharing one free key got "503 ResourceExhausted". Model calls now wait and retry, and the benchmark runs one job at a time.

## Accomplishments that we're proud of

- The full chain runs on its own, from a complaint typed in the widget to a guarded pull request, on code we did not write.
- The model cannot fake a result. "Reproduced" needs machine evidence; an unreadable model reply never decides anything; a fix counts only when code replays the original steps and the bug is gone.
- We publish our misses. The real-bug table shows every case, including the ones we lost.

## What we learned

- Simulate conditions, don't role-play them. A model told "you are on a slow phone" finds nothing; a browser that really is slow finds the bug.
- Separate acting from judging, and judge with evidence, not the model's opinion of its own work.
- Real apps break agents in boring ways: loading screens, page reloads, alias imports, rate limits. A benchmark on real bugs found them in a day.

## What's next

1. Five design-partner teams, and pull requests merged by people who are not us.
2. Native Android apps, with an emulator in GitHub Actions and the same evidence model.
3. Sector packs with real rules: payments, health, government accessibility law.

## Try it

- Repo: https://github.com/yashasviyadav30/complaint-replay
- Live dashboard: [FILL once hosted]
- Recorded demo (real cases, read-only): https://yashasviyadav30.github.io/complaint-replay/
