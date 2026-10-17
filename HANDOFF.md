# Handoff: where this project stands

Read this first in a new session. The plan is `plan.md` (phases, gates, cut list). Deadline: Oct 30, 2026,
10:00 am PDT = 10:30 pm IST (submit Oct 29). v0 history (Oct 11-15) is in git; this file covers the real product.

## START HERE (written Oct 17 evening, end of the long session c15f4155)

**How to work with this user** (also in memory files, which load automatically):
- Reply in English only (user writes Hinglish). IELTS rule: if *their own* sentence has a real grammar error, one line
  "✏️ Corrected: ..." then `---`, then the answer. Plain English everywhere (see `~/.claude/CLAUDE.md`).
- Keep working without check-ins until the project is complete; stop only for steps only the user can do.
- Keep brainstorming WOW / user-centric ideas continuously (memory `keep-brainstorming-wow`).
- Never submit, publish, post or send anything in the user's name without an explicit yes. Budget ₹0.
  Never type card or bank details; the user adds the card themselves.
- Run one pytest suite at a time (shared `workspace/badshop`); commit only after a green run.
- The GateGuard hook asks for facts before each first edit of a file and before some Bash calls: state them, retry.
- Heredoc/python string edits turn `\n` inside strings into real newlines: use the Edit tool for those.

**State right now**
- Code: all committed and pushed to `main` (last: the replay film, f387fcb). 161 tests.
- Real-bug benchmark (Actual Budget, 8 bugs, GitHub Actions `real-bugs.yml`): published in README +
  `benchmarks/real-bugs.md` from run 11: strict solved 0/8, fixed and guarded in any file 1/8 (8733, diff in
  `benchmarks/real-bugs-8733-our-fix.diff`). Run 13 (39040748961) was running with all fixes. Read a case:
  `gh run download <run> --repo yashasviyadav30/complaint-replay -n case-<pr> -D <dir>`.
  Reproduces reliably: 8733 (typed_value_lost) and 9071 (new evidence `picker_not_opened`). Structurally hard
  (notes in `benchmarks/real-bugs.json`): 8926 missing feature, 9107 app-specific balance maths, 9064 needs a
  reconciled transaction (lock icon, no text), 9038 needs a non-current month. 8570 (keyboard) and 8765 (bulk
  edit) are possible but the twin still doesn't get there.
- Token Factory: the user registered on Devpost and submitted the $25 credit form (code NEBIUS-DEVPOST-GLOBAL26);
  another $25 via the Nebius Builders Program. Token Factory's console demands billing details + a card before
  any API key ("temporary $0 authorization"). RuPay fails because Nebius bills through Stripe (Visa/Mastercard
  only). The user is solving this (Visa/Mastercard debit with international use on, then off; or Nebius Discord).
  When `NEBIUS_API_KEY` is in `.env`: one test call, then set a hard token cap; benchmarks stay on the NVIDIA key.
  Model and embedding names are looked up in the provider's own catalog, so the switch needs no code change.

**In flight when the session ended**
1. Replay film (WOW idea #1): `replay/film.py` makes a captioned GIF, one frame per step, the control about to be
   used boxed in yellow, last frame red ("Found: ...") or green ("the problem is gone"). Wired into
   `agent.replay(film=...)`, `guard.run_guard(film=..., ending=...)`, `investigate` (`case["films"]` before/after)
   and the PR body (films play inline on GitHub; stills are the fallback). Committed (f387fcb), suite green.
   NEXT: show films in the dashboard case view (server must serve `.gif` from the shots dir) and on the
   reporter's status page ("here is your problem, as you saw it; it's fixed"), then use them in the demo video.
2. Benchmark run 13: read each case, fix what misses teach, rerun.

**WOW / user-centric list (ranked, Oct 17)**: (1) replay film, building; (2) "hear what a blind user hears":
screen-reader audio of the page for screen-reader bugs; (3) MCP server so coding agents (Claude Code, Cursor,
Copilot) can run replays and guards; (4) "Who does this PR hurt?": pre-merge replay under the real users'
device/network/language mix from widget data; (5) voice complaints in the widget; (6) bug cost in rupees.

**What "project complete" means here** (user agreed): benchmark as good as it honestly gets; deploy-ready
(one command, the user only signs up); fresh-machine run of the README (done Oct 17: install from GitHub,
`crp init`, `crp setup`, first replay all worked); final README/write-up numbers (`submission/writeup.md` has
`[FILL]` markers). Then: Token Factory key, product name, hosting, Devpost draft (after the name), video
(script `submission/video-script-v1.md`), submit Oct 29 (user clicks).

## State after the night of Oct 16-17

Phase 1 tasks 1.0-1.7 (except 1.8) and most of 1.9/1.10 are built and tested (`uv run pytest -q`: 95 passing).

| Plan task | State |
|---|---|
| 1.0 MCPs | Context7 and Playwright MCP added to user config (load next session) |
| 1.1 Any URL | `complaint-replay.toml` per repo (`replay/project.py`); any start command or a running URL; saved login via `crp auth`; hints for test data |
| 1.2 Conditions | 207 device profiles, 8 network profiles, locale/timezone/dark/forced colors/reduced motion/zoom, keyboard-only and screen-reader twins; stated needs read from the complaint by Nemotron |
| 1.3 Evidence | 12 new collectors with fixture tests (`tests/test_collectors.py`): covered, clipped, overflow, broken image, slow request/page, layout shift, stuck loading, redirect loop, RTL, language mismatch (fastText, any language), focus, keyboard reach, unclear names |
| 1.4 Fix + PR | Evidence-guided file picking for big repos, CRLF-safe patches, PR from a bot identity to `origin` only, guard JSON committed; proof = exact steps replayed on the fix (no model) |
| 1.5 Action + service | `action.yml`, `crp` CLI, workflow template (`crp init`), multi-project server with widget keys, signed callbacks, GitHub App + login code (untested live: needs the user's App), Docker self-host (built and smoke-tested) |
| 1.6 Languages | 400 synthetic complaints in 20 languages; triage 98% held-out; cross-language grouping 97% top-1 (`benchmarks/triage.md`) |
| 1.7 Dashboard | Projects, setup wizard, impact-ranked board, PR links, sign-in; guideline review done; Lighthouse at 360 px (Oct 16): accessibility 100, best practices 100, no sideways scroll on any view |
| 1.9 Close the loop | Widget in 17 languages with RTL; reporter sees status ("fixed"); sector field on projects (no sector rules yet) |
| 1.10 Hardening | Security review done and fixed (commit "security: ..."); not deployed yet |
| 1.8 Real-bug benchmark | Running in GitHub Actions on 8 real Actual Budget fixes (see status below); score not final |

## Oct 17 (day): Phase 1 finish + Phase 2 started

- New evidence: taps that did nothing (no_response), taps something else intercepted (tap_blocked).
- Monorepos: dependency folders linked at any depth in branch copies.
- Phase 2: bring-your-own model (REPLAY_BASE_URL), failed fixes become GitHub issues with the guard as
  acceptance test, replay from issues labelled `replay` with a reply on the issue (proven: demo issue #5 -> PR #6),
  team chat notifications (Slack-compatible), support-desk inbox and Sentry webhook intake (project secret).
- Sector packs: public (audit everyone, strict masking, no screenshots), fintech (strict masking).
- Teams' own checks: `checks = ["checks/x.js"]` in complaint-replay.toml.
- Hosting prep: Dockerfile.server (920 MB, no browser), render.yaml, DEPLOY.md, Postgres extra.
- Real-bug benchmark harness `scripts/bench_real.py` on Actual Budget (`benchmarks/real-bugs.json`, 8 real fixes
  reverse-applied). First try exposed a false "fixed" (judge cited unrelated evidence) -> stricter "solved" =
  fixed AND same file as the real fix. Do not run heavy jobs (tests, docker builds) while it runs: Actual's dev
  server then misses its start timeout (`CRP_START_TIMEOUT=300`).

## Real-bug benchmark status (Actual Budget)

- Pass 1: 0/8 solved (kept in `benchmarks/real-bugs-pass1.md`). Misses were mostly navigation (app still loading,
  wandering, Tab/scroll loops) and missing evidence types.
- Engine lessons added since: wait-until-ready, visited-pages memory, stuck detection (not for keyboard), nameless
  controls labelled by nearby text, chrome bars not "covering", scroll from screen centre, new evidence
  (no_response, tap_blocked, typed_value_lost, wrong_option_chosen), judge rule + per-item skeptic check against
  "obstacle on the way" proofs, fix retries see the full files the first attempt tried to edit, tolerant JSON.
- Pass 3 (local) stopped part way: the laptop is too slow and short on memory for a big dev server.
- Moved to GitHub Actions: `.github/workflows/real-bugs.yml` (start it from the Actions tab; one job per bug,
  report job writes the table). Cases run one at a time: three jobs sharing the free NVIDIA key got
  "503 ResourceExhausted"; model calls now wait 30/60/120/240 s on a busy server (`patiently` in `replay/llm.py`).
  With a Token Factory key, raise `max-parallel`.
- Cloud runs 3-4 (Oct 16) taught, each now fixed with a test: fixer missed shared components (evidence now
  names the element, picker follows imports incl. `#alias/` paths, 100k-char file cap); twin history showed
  bare numbers (now names); cold Vite page hung after reload (twin refreshes once); a tap's own popover
  counted as "tap blocked"; made-up control numbers (clear error now); fixer ran out of tokens while reasoning
  (32k, says so); slow-page evidence read as "still loading" (wait result says when nothing loads).
- Run 5 (38911600083): 0/8. Its report showed the real cause of much wandering: with no REPLAY_MODEL (CI and every
  customer's Action) the twin ran on `nemotron-3-nano-omni-30b-a3b-reasoning`. Default is now Nemotron 3 Super.
  Also fixed from run 5: disabled controls are never proof (Actual disables fields while the amount is edited:
  the 9071 and 8926 "reproductions" were that); new controls marked (new); covered taps explained; patches match
  despite changed indentation; keyboard twin sees the screen and can hold Tab; evidence brief per kind.
- Known hard cases: 9107 needs a domain check (running balance maths); 9038 needs a non-current month on screen;
  9071's native date picker is invisible to a headless browser.
- Run 6 (38928497833): first run on Super with every fix. Read cases with `gh run download <run> -n case-<pr>`.
- Runs 6-10 (Oct 16-17), all 0/8 but each miss now honest. Fixed from them, each with a test: taps behind an open
  dialog are not evidence; load-speed evidence only proves speed complaints (one model question per case); React
  dev warnings are not console errors; the twin's own "reproduced" claim goes through the judge; fixer may not edit
  tests/mocks/guards; second fix round with the proof's evidence when the guard rejects a patch; new tabs are a
  response; key presses report the new focus; same-named controls get their row; label-drawn switches and
  `tabindex=0` divs are controls; a tap on a disabled control still lands (ends the edit in progress); refuse a
  sixth tap on one control; 80 min per case.
- 8733 reproduces for real every run (amount lost after tapping Cleared); the fixer sees table/utils.ts but keeps
  patching its caller. Actual hints (public, `benchmarks/actual-complaint-replay.toml`) now explain scheduled rows,
  the '✓' sort header and which transactions show a Reconciled switch.
- Second benchmark app: rule = open source, one dev command, no database or login, 2026 fixes visible on the page,
  take every fix in a window. Checked Oct 17 and rejected: IT-Tools (fixes 2023-24, likely in model training),
  Homepage (fixes need outside services), Uptime Kuma and memos (login + setup first). Still open.
- Lesson for me: never run two pytest suites at once here (shared `workspace/badshop`), and commit only after a
  green run.
- Memory: the laptop ran out once (Chrome + Docker + two Actual dev servers). Docker Desktop is stopped; don't
  run heavy jobs during a pass. Restart a killed pass only when the user says so.

## Proven end to end (all real, all reproducible)

Demo repo (private): `yashasviyadav30/crp-demo-shopping-cart`, an unchanged copy of an MIT app with real a11y bugs.
- PR #1: cart button read only as "1" (local `crp replay --fix --pr`; CI: guard passes, "catches the bug on origin/main").
- PR #2: "+" and "−" buttons unnamed, run fully in GitHub Actions (workflow_dispatch).
- PR #3: product images without alt text. FULL LOOP: report over the internet -> server -> repository_dispatch ->
  Action reproduces as a screen-reader user (need read from the complaint) -> fix -> guard -> PR -> status back
  -> the reporter's widget status says "fixed".
- A Hindi screen-reader complaint went through the hardened loop at the end of the night (see the run list).

## Run things

```bash
uv run uvicorn server.app:app --port 8200          # service + dashboard + demo shop (local only without login)
uv run crp replay "..." --repo <app> --user screen_reader --fix --pr
docker compose up                                   # self-host, bound to 127.0.0.1
uv run python scripts/train_triage.py               # triage + cross-language numbers -> benchmarks/triage.md
uv run python bench.py 3                            # demo-shop benchmark (planted bugs)
```

Full-loop test setup used tonight: `~/tools/cloudflared/cloudflared.exe tunnel --url http://127.0.0.1:8200`, then
the server with `PUBLIC_URL=<tunnel url>` and `GITHUB_TOKEN=$(gh auth token)`, project linked to the demo repo.

## Lessons (don't relearn these)

- With an `upstream` remote, `gh pr create` targets the upstream repo. Always pass `--repo` from `origin` (pr.py does).
- Repos block Actions from opening PRs by default: Settings > Actions > "Allow GitHub Actions to create and approve pull requests".
- PRs made with the Actions token don't trigger other workflows; the GitHub App token does.
- A model-driven "proof" replay once proved a fix by never reaching the broken screen. Proof is now the exact steps.
- The judge over-cited real but unrelated bugs; evidence now says where each control is, and the prompt says real apps have several bugs.
- Chrome blocks public pages from loading scripts on 127.0.0.1 (Private Network Access): test widgets same-origin.
- Python 3.14 has no fasttext-predict wheel: Docker pins 3.13 (`.python-version`).
- A tunnel connects from 127.0.0.1: "local only" checks must ignore requests with forwarding headers.
- The GateGuard hook asks for facts before each first edit of a file; answer and retry.

## Next, in order

1. Finish the replay film (commit after green; dashboard + reporter status page), then WOW ideas #2 and #3.
2. Real-bug benchmark: keep reading runs and fixing what misses teach; republish README + table + write-up numbers.
3. Deploy-ready: check `Dockerfile.server` + `render.yaml` + `DEPLOY.md` still work; the user only signs up.
4. When the Token Factory key exists: one test call, token cap, one small proof run on Token Factory; README note.
5. Video and write-up (1.11) from Oct 26; freeze Oct 28; submit Oct 29 (user clicks).

## User must do

- Token Factory key: add a Visa/Mastercard (international use on for the $0 check, then off) or ask the Nebius
  Discord (a ready message was drafted in the Oct 17 chat). Decide by Oct 22, hard stop Oct 25.
- Pick the product name by Oct 18 (Complaint Replay vs Black Campus/Compass), then create the Devpost draft
  ("Start project"); Claude prepares the field texts, never submits.
- Sign up on Render (free) and click the GitHub App creation; Claude does the rest.
- Decide whether `crp-demo-shopping-cart` becomes public (judges can't open private PR links).
- Rotate the NVIDIA and Tavily keys after the hackathon (they were pasted in chat earlier).
