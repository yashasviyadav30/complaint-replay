# Judging criteria map

Four criteria, equal weight (Devpost rules). Tie-break order: Technological Implementation first.

| Criterion | Evidence in the project | Where judges see it | Gap and fix |
|---|---|---|---|
| Technological Implementation | Three Nemotron roles with different settings (navigator and judge with thinking off, fixer with reasoning on); browser under real conditions; machine-only evidence; fix on a branch copy; guard that must pass on the fix and fail on the old code; 26 tests; `bench.py` results | Video 1:35-2:15; write-up "How we built it" and "Challenges"; README results table | Benchmark ran on NVIDIA's API catalog, not Token Factory. Fix: re-run `bench.py 3` on Token Factory before submitting and update the numbers |
| Design | A complete product, not a script: widget on the store, case board, case detail with screenshots, evidence, diff, proof and guard; dark and light; guideline review done | Video 0:20-1:35 (whole flow on screen); screenshots 1-4 | Live link: only a recorded read-only demo on GitHub Pages unless a host account is made. Frame it honestly as "recorded real cases" and show the live flow in the video |
| Potential Impact | "Can't reproduce" is 13-24% of bug reports (ICSME 2020); a large share comes from device, network or settings differences, which is exactly what the twin copies; target user is small web teams without QA | Video 0:00-0:20; write-up "Inspiration" and first two sentences | No real users yet. Do not claim any. Say who it is for and why, with the cited research |
| Quality of the Idea | Starts from real complaints and silent frustration, copies the complainer's conditions, and ends in proof + fix + a guard test. Research reproduces bug reports from clean developer text; tools record sessions or cluster feedback; none we found does the whole chain from a customer's words | Write-up "What it does"; video 2:15-2:35 | Keep the novelty claim modest: "we did not find a tool that does the whole chain" (true), not "first ever" |

## Smallest fixes, ranked by points per hour

1. Token Factory key + re-run benchmark (required by the rules, protects Technological Implementation). About 1.5 hours of machine time.
2. Record the video from a real run (Design + everything else). About 2 hours.
3. Live hosting with a real Break It button (Design). Needs a host account the user must create; about 1 hour after that.
