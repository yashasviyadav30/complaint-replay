# Real bugs: Actual Budget

Measured 2026-10-16 with `uv run python scripts/bench_real.py <actual checkout>`, model `nvidia/nemotron-3-super-120b-a12b`. Each bug was fixed upstream; it is re-created by reverse-applying that fix to today's code, and the complaint is written from the real report. "Same file" means our fix edited a file the real fix edited. Every case is listed, misses included.

| Upstream fix | Complaint | User | Result | Proof (evidence kinds) | Same file as real fix | Time |
|---|---|---|---|---|---|---|
| [#9071](https://github.com/actualbudget/actual/pull/9071) | On my Android phone, when I add a transaction and tap the date, the ca… | Pixel 7 | error | - |  | 0 min |
