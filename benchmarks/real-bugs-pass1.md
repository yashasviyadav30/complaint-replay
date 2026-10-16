# Real bugs: Actual Budget

Measured 2026-10-16 with `uv run python scripts/bench_real.py <actual checkout>`, model `nvidia/nemotron-3-super-120b-a12b`. Each bug was fixed upstream; it is re-created by reverse-applying that fix to today's code, and the complaint is written from the real report. "Same file" means our fix edited a file the real fix edited. Every case is listed, misses included.

**Solved 0 of 8.** Solved means fixed and guarded AND our fix edited a file the real fix edited. A "fixed" with a different file is counted as a miss: the guard may have proven the wrong thing.

| Upstream fix | Complaint | User | Result | Proof (evidence kinds) | Same file as real fix | Solved | Time |
|---|---|---|---|---|---|---|---|
| [#9071](https://github.com/actualbudget/actual/pull/9071) | On my Android phone, when I add a transaction and tap the date, the ca… | Pixel 7 | error | - |  | no | 10 min |
| [#9064](https://github.com/actualbudget/actual/pull/9064) | On my phone the Reconciled switch on a transaction does nothing when I… | Pixel 7 (412x839) | not_reproduced | - |  | no | 2 min |
| [#8926](https://github.com/actualbudget/actual/pull/8926) | On my phone I picked the wrong payee for a new transaction and now the… | Pixel 7 | error | - |  | no | 5 min |
| [#9107](https://github.com/actualbudget/actual/pull/9107) | On my phone, with hide reconciled transactions turned on, the balance … | Pixel 7 (412x839) | not_reproduced | tap_blocked |  | no | 1 min |
| [#8733](https://github.com/actualbudget/actual/pull/8733) | On my phone I type the amount for a new transaction and then tap the C… | Pixel 7 (412x839) | not_reproduced | - |  | no | 3 min |
| [#8570](https://github.com/actualbudget/actual/pull/8570) | I only use the keyboard. When I choose a category for a transaction wi… | desktop 1280x800, keyboard only, no mouse | not_reproduced | - |  | no | 11 min |
| [#8765](https://github.com/actualbudget/actual/pull/8765) | When I select several transactions and use bulk edit to change the dat… | desktop 1280x800 | not_reproduced | - |  | no | 11 min |
| [#9038](https://github.com/actualbudget/actual/pull/9038) | In the guided tour, the To Budget step highlights nothing I can see. T… | desktop 1280x800 | not_reproduced | - |  | no | 4 min |
