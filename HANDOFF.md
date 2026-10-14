# Handoff: where this project stands

Read this first in a new session. Plan and scoring: `~/hackathon-ideas/nebius-nvidia-global-ai-2026.md`.
Beginner explainer: `../IDEA-EXPLAINED.md`. Deadline: Oct 30, 2026, 10:00 am PDT (submit Oct 29).

## Done (all committed, `uv run pytest -q` = 20 passing)

- BadShop demo store (`badshop/`), 5 planted bugs (`replay/bugs.py`: ids 1, 4, 7, 10, 15).
- Real user conditions (`replay/conditions.py`) + `twin_condition(env)` built from widget data.
- Browser session with machine evidence (`replay/browser.py`). The model can only cite evidence.
- Navigator + separate evidence judge (`replay/agent.py`, `replay/llm.py`), hard token budget.
- Fix on a branch copy + proof replay (`replay/fix.py`, `replay/investigate.py`).
- Live service (`server/app.py`): widget complaints -> case -> investigate in background;
  `/api/cases`, `/api/live`, `/api/break` (random secret bug), `/api/reset`; serves `widget.js`.
- Kill switch passed: all 5 bugs reproduce -> fix -> prove, 0 false alarms (Oct 12).

## Run

```bash
uv run uvicorn server.app:app --port 8200   # also starts live BadShop on :8100
uv run python pipeline.py 4                 # one planted bug end to end from the CLI
uv run python risk_test.py                  # 5 bugs, buggy vs clean
```

## Lessons (don't relearn these)

- Nemotron "thinking" ate max_tokens -> empty replies. Browser steps run with thinking off.
- Chrome CPU throttling made timers fire late -> timeout bug was a coin flip. Removed.
- CDP network throttling was ignored -> latency is added in a Playwright route instead.
- Navigator loops when nothing visibly changes -> it now gets "nothing visible changed" / repeat notes.
- Model ids that list but 404 on the free NVIDIA tier: llama-3.1-nemotron-ultra-253b-v1, nemotron-nano-3-30b-a3b.
  Working: nemotron-3-super-120b-a12b (navigator + fixer), nemotron-3.5-lightning, nemotron-3-ultra.

- Dashboard (`dashboard/`, React + Vite + Tailwind v4, built into `dashboard/dist`, served by the service at /):
  case board, case detail (evidence, fix diff, proof, steps), Break It / Reset. Guideline review done.
- Real customer flow verified in Chrome (Oct 12): planted bug 15, used the shop, complained in the widget,
  case went reproducing -> fixing -> proving -> fixed on its own.
- Public repo: https://github.com/yashasviyadav30/complaint-replay (Apache 2.0 detected).

- Guard step (`replay/guard.py`): proof replay saved as JSON test in the fix branch; must pass on the fix
  AND fail on the old code -> stage "guarded". Verified on bug 15 (Oct 12).
- Live service uses its own folder `workspace/live/badshop`; CLI/tests use `workspace/badshop`;
  temp shops get free ports. Never run the bench while relying on a stale live process.
- `bench.py N`: N runs per bug + clean-shop false-alarm check -> `results/bench.md` (first run started Oct 12).

## Done Oct 13

- Before/after screenshots per case (`results/cases/shots/`), shown in the case detail.
- Proof is decided by the evidence that proved the bug (`fix_proven`), not the proof run's verdict; judge ignores
  errors the twin caused itself. 26 tests.
- Read-only recorded demo on GitHub Pages: https://yashasviyadav30.github.io/complaint-replay/
  (`bash scripts/deploy_demo.sh` re-exports `results/cases` and redeploys).
- Submission materials in `submission/`: writeup, video script, criteria map, feedback, checklist.
- Demo video: real run recorded with `scripts/record_demo.py`, cut per `video/README.md`, HyperFrames project in
  `video/film/`, render -> `video/complaint-replay-demo.mp4` (captions only, ~1:55).

## Done Oct 13 (evening)

- Tavily research before each fix (`replay/research.py`), sources shown in the case; needs `TAVILY_API_KEY`.
- Bugs 3 (double tap -> two orders, `duplicate_request` evidence) and 13 (elderly 200% zoom hides Pay). 7 bugs total.
- Fixed an intermittent shutdown hang: route handlers are released (`unroute_all`) before the browser closes.
  A one-off bug-7 test failure was seen once under load; tests now print the evidence if it recurs.
- Guards are built from the reproduction steps (keeps the double tap). A rejected fix edit gets one retry with
  the reason. Previous 7-bug run (before the retry): 20/21 reproduced, 18/21 fixed, 18/21 guarded, 0 false alarms.
- Oct 14 ~01:50: NVIDIA free tier rate-limited Nemotron 3 Super (HTTP 429, per model; Lightning still OK).
  A background job polls Super every 5 min and then runs the final bench. If bench.log shows RateLimitError,
  wait and re-run `uv run python bench.py 3`. The Token Factory key would remove this limit.
- FINAL `bench.py 3` (7 bugs) started Oct 14 ~01:10 -> `results/bench.md`. When done: put its table and totals in
  README "Results", `submission/writeup.md` ("On five realistic bugs..." line, now 7), `submission/video-script.md`
  numbers, and the video results card (`video/film/index.html` #results) then re-render; redeploy demo
  (`bash scripts/deploy_demo.sh`).

## Oct 14: duplicate-complaint grouping (IN PROGRESS, uncommitted until calibration finishes)

- Why: one bug, many complaints in many languages -> one investigation + "xN reports"; board sorts by reports.
- No NVIDIA GPU on this laptop (AMD 780M, 20 GB) -> no on-device LLM training; fine-tuning would belong on Nebius
  post-training (needs the Token Factory key). Instead: data-fitted settings, measured on a held-out half.
- Data: `data/complaints_labeled.json` (57 hand-written complaints, 7 bugs + unrelated, EN/Hinglish/Hindi).
- Measured so far (test half): embedding cut only P0.61/R0.71; embedding cut + Nemotron verifier P0.86/R0.75 (F1 0.80);
  normalise-then-embed with a cut: worse (F1 0.56). Fixed cuts are fragile (Hinglish vs English sim 0.20).
- Current design: `replay/grouping.py` find_duplicate = embed (raw or normalised, per settings) -> verify top-k
  nearest open cases with Nemotron 3.5 Lightning. `scripts/calibrate_grouping.py` simulates arrival order, picks
  embed_text/top_k on the fit half, reports test P/R into `replay/grouping.json`.
- Server: `group_into_existing()` in `server/app.py`; vectors in `results/vectors.json`; dashboard shows
  "xN reports", sorts by reports, lists "Also reported by" in the case detail (built).
- TODO after calibration: delete now-unused fit_threshold/shortlist_threshold/best_match/threshold from
  grouping.py and update tests/test_grouping.py; restart service and re-run the A/B/C live check (A Hinglish OTP,
  B English OTP -> must join A; C delivery -> separate); add the grouping numbers to README; commit + push.

## Next, in order

1. When the Token Factory key arrives: set `NEBIUS_API_KEY`, re-run `bench.py 3`, update README + writeup +
   video results card and add "on Nebius Token Factory" to the video captions; re-render.
2. Upload the video to YouTube (user's account) and add the link to README and Devpost.
3. Optional: voiceover in the user's voice (needs a 1-2 min sample), live hosting (needs a host account).
4. Paste `submission/writeup.md` + `feedback.md` into Devpost; final checklist; user clicks Submit.

## Blockers (user side)

- Submission must call Nebius Token Factory. Dev uses a free build.nvidia.com key (`NVIDIA_API_KEY`).
  User has no usable card; waiting on organisers (Discord) or the ATM card. Switch = one line in `.env`.
- Product name is a working name; user will rename later.
