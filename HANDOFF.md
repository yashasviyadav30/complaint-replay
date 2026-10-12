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

## Next, in order

1. Dashboard (React + Vite + Tailwind, `dashboard/`): case board Heard -> Reproduced -> Fixed -> Guarded,
   case detail with evidence cards, steps, diff, Break-it button.
2. Screenshots at evidence time (before/after) for the case detail and the video.
3. Guard: save each proven replay as a re-runnable test file.
4. Repeat-run success rates for the README (real numbers, not best run).
5. GitHub public repo (Apache 2.0), deploy, README for judges, video, Devpost write-up.

## Blockers (user side)

- Submission must call Nebius Token Factory. Dev uses a free build.nvidia.com key (`NVIDIA_API_KEY`).
  User has no usable card; waiting on organisers (Discord) or the ATM card. Switch = one line in `.env`.
- Product name is a working name; user will rename later.
