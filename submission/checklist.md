# Pre-submit checklist

Deadline: **Oct 30, 2026, 10:00 am PDT = 10:30 pm IST.** Target: submit Oct 29. Devpost allows edits until the deadline, so submit a draft early.

## Hard blocker

- [ ] **Token Factory key in `.env` (`NEBIUS_API_KEY`).** The rules require a runtime call to Token Factory. Until then every claim about Token Factory in the write-up and video is not yet true.
- [ ] Re-run `uv run python bench.py 3` on Token Factory. Update the README results and the "measured on" note.

## Required by the rules

- [x] Public repo with an open-source license visible at the top (Apache 2.0, detected by GitHub)
- [x] README with setup steps and where Nemotron and Token Factory are used
- [ ] Working demo URL (recorded demo on GitHub Pages; a live host is better if an account is made)
- [ ] Demo video: public YouTube, 3:00 or shorter, shows Token Factory and Nemotron being used
- [ ] Project description pasted from `writeup.md`
- [ ] Track selected: Coding and Agentic Engineering
- [ ] Feedback section pasted from `feedback.md`

## Final checks

- [ ] Repo searched for secrets once more (`git grep -n "nvapi-\|sk-"` returns nothing)
- [ ] Video link opens in a private window
- [ ] Demo link opens when logged out
- [ ] Every number in the write-up matches `benchmarks/demo-shop.md`, `benchmarks/real-bugs.md` and `benchmarks/triage.md`
- [ ] No `[FILL]` left in `writeup.md`
- [ ] Product name final in the write-up, README, widget and video
