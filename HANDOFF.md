# Handoff: where this project stands

Read this first in a new session. The plan is `plan.md` (phases, gates, cut list). Deadline: Oct 30, 2026,
10:00 am PDT = 10:30 pm IST (submit Oct 29). v0 history (Oct 11-15) is in git; this file covers the real product.

## START HERE (written Oct 17 evening, end of the long session c15f4155)

If a detail is missing here, the full transcript of that session (≈209 MB, JSON lines; search it with grep, never
read it whole) is `~/.claude/projects/C--Users-yasha-Downloads-Nebius-x-NVIDIA-Global-AI-Hackathon/c15f4155-4d0f-4d91-a968-a421246165b9.jsonl`.

**How to work with this user** (also in memory files, which load automatically):
- Reply in English only (user writes Hinglish). IELTS rule: if *their own* sentence has a real grammar error, one line
  "✏️ Corrected: ..." then `---`, then the answer. Plain English everywhere (see `~/.claude/CLAUDE.md`).
- Keep working without check-ins until the project is complete; stop only for steps only the user can do.
- Keep brainstorming WOW / user-centric ideas continuously (memory `keep-brainstorming-wow`).
- Never submit, publish, post or send anything in the user's name without an explicit yes. Budget ₹0.
  Never type card or bank details; the user adds the card themselves.
- Run one pytest suite at a time (shared `workspace/badshop`); commit only after a green run.
- Stopping a background task (TaskStop) kills its shell, NOT the pytest inside: an orphan full suite ran from
  Oct 17 22:01 to Oct 18 15:28 beside every later run (random failures, hour-long runs). Before trusting a slow or
  odd run: `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` and stop stale `pytest.exe` processes.
- The GateGuard hook asks for facts before each first edit of a file and before some Bash calls: state them, retry.
- Heredoc/python string edits turn `\n` inside strings into real newlines: use the Edit tool for those.

**How the work runs (the user asked the next session to work exactly like this, without waiting for them)**
- Never sit idle and never ask "should I continue?". While something slow runs, do the next useful thing.
- Cloud benchmark loop: start a run, watch it with the Monitor tool, read each case as it lands, fix what it
  teaches (with a test), commit after a green suite, start the next run. Re-arm the monitor when it expires.
  ```bash
  gh workflow run real-bugs.yml --repo yashasviyadav30/complaint-replay      # then get the id:
  gh run list --repo yashasviyadav30/complaint-replay --workflow real-bugs.yml --limit 1 --json databaseId
  # Monitor command (one event per finished case; ends when the run completes):
  prev=""; while true; do s=$(gh run view <ID> --repo yashasviyadav30/complaint-replay --json jobs,status --jq '.status as $st | (.jobs[] | select(.status=="completed") | "\(.name): \(.conclusion)"), "run: \($st)"' 2>/dev/null | sort); if [ -n "$s" ]; then diff <(echo "$prev") <(echo "$s") | grep '^>' | sed 's/^> //'; prev=$s; fi; echo "$s" | grep -q "run: completed" && break; sleep 120; done
  gh run download <ID> --repo yashasviyadav30/complaint-replay -n case-<pr> -D <scratch dir>
  uv run python scripts/show_case.py <scratch dir>/real-bugs/pr<pr>.json
  ```
- Long test suites (`uv run pytest -q`, 6-40 min on this laptop) go in a background shell; one suite at a time.
  A test that fails only in the full run but passes alone (`pytest --lf`) has been timing flakiness under load.
- Before building anything: quick ranked brainstorm (WOW, ₹0, days left, real user value), then build the best.
- Check every claim before writing it (git log for counts, a real run for behaviour, docs/web for facts).
- Tell the user, in short plain English, what changed and why after each meaningful step; they read along.

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

**Done in the Oct 17 night session (session 700d7840)**
- Films finished: dashboard case view plays them (`<picture>`: still for reduced motion), server accepts `films` in
  progress updates (per-entry name check, `.gif` allowed), sweeps them, and the reporter's status returns
  `films.after` once fixed (only files on this server: a PR branch may be private); widget shows "Watch it
  working now" in all 17 languages. `crp replay` without `--fix` now records a film too.
- WOW #2 done the ₹0 way: screen-reader replays keep `replay.heard` (the last screen's aria snapshot in
  screen-reader words, `agent.spoken()`); PR body has it in a <details>; dashboard "What a screen reader user
  hears" with a Listen button (browser `speechSynthesis`, no files, no dependency). Dropped when a project keeps no
  screenshots.
- WOW #3 done: `crp mcp` (`replay/mcp_server.py`, extra `complaint-replay[mcp]`, mcp 2.3 `MCPServer`): tools
  `replay_complaint`, `run_guards`, `find_devices`; CLI output captured, never on the protocol's stdout;
  test spawns the real server over stdio. README documents `claude mcp add complaint-replay -- crp mcp`.
- From run 13: a control number from a closed menu is refused by name without spending a step (9107 burned 5);
  fixer rule "fix the shared component that draws the control" (9071's real fix is `MobileForms.tsx`
  `showPicker()`, ours patched the screen; 8733 same pattern); cases record `fix.shown` and `show_case.py` says
  whether the real fix file was shown. 8926's real fix is a new feature across 6 files: stays an honest miss.

- Run 13 final (39040748961, before tonight's fixes): solved 0/8, fixed in any file 0/8 (run 11 had 1/8).
  Fixed after it, with tests: a tap reports the control's new state ("it is now checked", "it now shows a mark",
  "its mark went away"; 8765 toggled one row 8 times on bare "ok"s) and no longer says "nothing visible
  changed" over it; keyboard twins' stop summary states their real budget (50, not 25); screen-reader name check
  ignores aria-hidden text and reads aria-labelledby (the demo cart was reported as "announced as '0'" while a
  screen reader says just "button").
- Demo cases re-recorded with films (bug 4: Pay off a 360 px screen; bug 10: screen reader + transcript), both
  guarded. Video script updated to use voice, Listen, films and MCP.

- Voice complaints in the widget (WOW #5): "🎤 Speak instead" in 17 languages, browser speech recognition, the
  user checks the text before sending; README privacy note (Chrome sends audio to Google; we keep none).
- Deploy check done (Oct 17 night): `Dockerfile.server` builds (978 MB) and serves health, dashboard, widget. Found
  and fixed: without PUBLIC_URL a complaint got a 500 and no status token (now kept + answered, case says what to
  set); on Render the address comes from RENDER_EXTERNAL_URL (removed PUBLIC_URL from render.yaml); running_app
  now stops whatever still listens on the app's port (a leaked server locked workspace/badshop and failed 8 tests).
  Docker Desktop stopped again afterwards.
- Run 14 (39051065827, on dc755ea) so far: 9071 "fixed" (guard passes on fix) but the guard did not fail on old
  code: it had dropped the disabled-but-landed tap (fixed: `TAP_LANDED` steps stay in guards); fixer still patched
  the screen although `MobileForms.tsx` was shown. 8926: refused claim ended the replay at step 3 (fixed: one more
  try). 9107: 11 taps behind an open menu (fixed: refusal lists the menu's controls; sighted twins have Escape).
  9064: honest miss. Fixer rule added for shared helpers (8733).

- Run 14 final: solved 0/8, fixed in any file 0/8. 8733 hit the 80 min cap with an empty error and its progress
  lost (fixed in bench_real.py: progress kept, "timed out after N min (last stage: ...)", cap 95 min; job limit is
  120). 8570 Tab-wandered 50 steps on the budget page; 8765 ticked budget-page boxes, never opened an account
  (navigation, not the new state note); 9038 walked the tour, highlight only off-screen in a non-current month.

- Run 15 (39061678952, on 76fadc0): **solved 1/8 strict** (first ever): 9071 guarded in MobileForms.tsx, the
  upstream file; our fix shows the calendar button instead of upstream's showPicker() (said in README + table,
  diff in `benchmarks/real-bugs-9071-our-fix.diff`). Published in README, `benchmarks/real-bugs.md`, write-up
  (only `[FILL]` left: live dashboard URL). README states results vary (8733 fixed in run 11, not in 13-15).
  Also from run 15: 8926 "proved" a bug by tapping a text box (fixed: focus in a text field is a response);
  8733 still patches the caller with utils.ts shown (a file-level ban would break same-file helper fixes: not
  done). 9107 now navigates to the right screen; needs an app-specific balance check (`checks`) to go further.

**In flight**
1. Next benchmark run (16) when there are new engine fixes; the hints change (be6a4f2) and the text-box fix
   (dc067c1) are not measured yet.
2. Demo dashboard (gh-pages) has no films/transcripts yet: record fresh demo-shop cases (one screen-reader), then
   `scripts/deploy_demo.sh` (it pushes gh-pages: ask the user first, it is public).

**WOW / user-centric list (ranked, Oct 17)**: (1) replay film, building; (2) "hear what a blind user hears":
screen-reader audio of the page for screen-reader bugs; (3) MCP server so coding agents (Claude Code, Cursor,
Copilot) can run replays and guards; (4) "Who does this PR hurt?": pre-merge replay under the real users'
device/network/language mix from widget data; (5) voice complaints in the widget; (6) bug cost in rupees.

**Oct 19 later: 3 roadmap features built (user asked), each tested end to end on a planted bug, 185 tests.**
iPhone/iPad and iPhone complaints replay in WebKit (Safari's engine; `engine` on Condition, `crp setup` installs
it, ready user `iphone`); slow users (`slow` on Condition, elderly is slow) read before each step and type key by
key, evidence `error_after_wait` (shop: OTP expires after 5 min; bug 16 = 10 s); payment interrupted (network
`tunnel`/flaky lose the first payment reply after the server took it, evidence `charged_twice`; Back/Reload
actions; shop has payment keys; bug 17 = new key per tap; ready user `train`). Money/date formats NOT built (next).
Linux check (run 39249081833, `new-features.yml`): all 3 guarded, Safari engine installs and runs in CI.
User said: no video changes now; stop after this. Video still shows the earlier feature set (still accurate).

**Oct 19: READY TO SUBMIT (user submits today).** Claims made honest (free NVIDIA API catalog; no Token Factory:
user won't add a card). Demo repo public; pinned issue #7 "Try it": a live `/replay` comment was reproduced, fixed
and guarded -> PR #8 (verified). README top: films, links, "what you won't find elsewhere"; repo description,
homepage, topics set. Write-up final, no [FILL]. Video `submission/complaint-replay-demo.mp4` (88 s, real screens,
real films, Windows speech reading the real screen-reader transcript). Left for the user: upload the video
(YouTube, public or unlisted), paste `submission/writeup.md` into Devpost, add the video link, Submit.

**Oct 18 decisions (user):** the benchmark loop is CLOSED: no run 17, no more benchmark runs; the published result
stays run 15 (1/8 strict). Name: **Complaint Replay** (final). Public demo page republished with films + Listen
(gh-pages, Oct 18). Next work, each with a fixed finish line, nothing else:
1. WOW "Try it yourself" (user picked A): `action.yml` + `replay/workflow.yml` accept `/replay [user] text` issue
   comments with a daily cap (`daily-limit`, default 20). Committed if the suite passed (see git log). STILL TO DO:
   copy the new trigger into `crp-demo-shopping-cart/.github/workflows/complaint-replay.yml`, check that repo for
   secrets, make it public (user agreed by picking A), open one pinned issue "Try it: comment /replay ...", and try
   one real comment end to end. Then a README line + video shot.
2. Premium README + repo (user asked Oct 18): films at the top, short "how it works", one-command setup; repo
   description, topics, social preview image. Finish line: those items, nothing more.
3. Then only user-unblocked items: Devpost draft text, Token Factory key, Render, video (Oct 26-27), submit Oct 29.

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

1. WOW ideas #1-#3 done. Next WOW: #4 "Who does this PR hurt?" (guards/replays under the real users' mix).
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
