# Handoff: where this project stands

Read this first in a new session. The plan is `plan.md` (phases, gates, cut list). Deadline: Oct 30, 2026,
10:00 am PDT (submit Oct 29). v0 history (Oct 11-15) is in git; this file covers the real product.

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
| 1.7 Dashboard | Projects, setup wizard, impact-ranked board, PR links, sign-in; guideline review done |
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

1. Real-bug benchmark (1.8): read the cloud run's table, fix what the misses teach, rerun, publish the score (misses too).
2. Hosting (1.10): decide the host (Nebius VM if the card works, else a free tier) and deploy with `PUBLIC_URL`,
   `SECRET_KEY`, `ADMIN_LOGIN`, then create the GitHub App via `/setup/github-app` (user clicks).
3. Re-run benchmarks on Nebius Token Factory once `NEBIUS_API_KEY` exists; update README numbers.
4. Sector packs (1.9): fintech first. Video and write-up (1.11) from Oct 26.

## User must do

- Post in the Nebius Discord about the card (Token Factory key); decide by Oct 22, hard stop Oct 25.
- Pick the product name by Oct 18.
- Decide whether `crp-demo-shopping-cart` becomes public (judges can't open private PR links).
- Rotate the NVIDIA and Tavily keys after the hackathon (they were pasted in chat earlier).
