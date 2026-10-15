# Triage and cross-language grouping

Measured 2026-10-16 with `uv run python scripts/train_triage.py`. Embeddings: `nvidia/nemotron-3-embed-1b`.

**Read this first:** the complaints are SYNTHETIC, written by Nemotron in 20 languages (`data/complaints_multilingual.json`), not collected from real users. Real complaints are messier; treat these numbers as a first check that nothing breaks across scripts, not as a benchmark.

Trained on 200 complaints, tested on 200 held-out complaints. The model is one average vector per class, fitted on a laptop CPU in under a second.

## Triage: bug, confusion, feature request or spam

Held-out accuracy: **98% (197/200)**

| Language | Correct |
|---|---|
| ar | 100% (10/10) |
| bn | 100% (10/10) |
| de | 100% (10/10) |
| en | 100% (10/10) |
| es | 100% (10/10) |
| fr | 100% (10/10) |
| hi | 100% (10/10) |
| hi-Latn | 100% (10/10) |
| id | 100% (10/10) |
| ja | 100% (10/10) |
| mr | 90% (9/10) |
| pt | 100% (10/10) |
| ru | 100% (10/10) |
| sw | 90% (9/10) |
| ta | 100% (10/10) |
| te | 100% (10/10) |
| tr | 90% (9/10) |
| ur | 100% (10/10) |
| vi | 100% (10/10) |
| zh | 100% (10/10) |

Mistakes (true label -> predicted):

- feature_request -> bug: 1
- ux_confusion -> feature_request: 2

**Known weakness.** Trained only on one kind of wish (dark mode) and tested on another (cash on delivery), the model scores: bug 100% (140/140), ux_confusion 95% (19/20), feature_request 0% (0/20), spam 100% (20/20). It learns topics it has seen, not the idea of a wish. The safe direction holds: a missed feature request costs one extra replay, it never hides a bug.

## Same bug, different language

For each held-out bug complaint, the most similar complaints written in OTHER languages are looked up. Grouping checks the top 3 with a Nemotron verifier, so top-3 is the ceiling for what it can merge.

Nearest is the same bug: **96% (135/140)**. Same bug among the top 3: **99% (138/140)**.

| Language | Top 1 | Top 3 |
|---|---|---|
| ar | 100% (7/7) | 100% (7/7) |
| bn | 100% (7/7) | 100% (7/7) |
| de | 100% (7/7) | 100% (7/7) |
| en | 100% (7/7) | 100% (7/7) |
| es | 100% (7/7) | 100% (7/7) |
| fr | 100% (7/7) | 100% (7/7) |
| hi | 100% (7/7) | 100% (7/7) |
| hi-Latn | 100% (7/7) | 100% (7/7) |
| id | 100% (7/7) | 100% (7/7) |
| ja | 100% (7/7) | 100% (7/7) |
| mr | 100% (7/7) | 100% (7/7) |
| pt | 100% (7/7) | 100% (7/7) |
| ru | 100% (7/7) | 100% (7/7) |
| sw | 57% (4/7) | 71% (5/7) |
| ta | 71% (5/7) | 100% (7/7) |
| te | 100% (7/7) | 100% (7/7) |
| tr | 100% (7/7) | 100% (7/7) |
| ur | 100% (7/7) | 100% (7/7) |
| vi | 100% (7/7) | 100% (7/7) |
| zh | 100% (7/7) | 100% (7/7) |
