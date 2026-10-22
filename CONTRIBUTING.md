# Contributing

## Set up

```bash
uv sync
uv run crp setup                 # installs Chrome's and Safari's engines for Playwright
cd dashboard && npm ci && cd ..
```

Copy `.env.example` to `.env` and add `NVIDIA_API_KEY` (free at build.nvidia.com) to run real replays. The test
suite does not need a key.

## Test

```bash
uv run pytest -q                 # engine, server and widget, in real browsers
cd dashboard && npm run lint && npm run build
```

The suite shares one copy of the demo shop under `workspace/`, so run one suite at a time.

## Changes

- A bug fix comes with a test that fails before the fix.
- New evidence kinds need a fixture test in `tests/test_collectors.py` and a label in `dashboard/src/labels.ts`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`,
  `refactor:`, `test:`, `ci:`.
- Claims in the README must be measured. If a number changes, update it with the command that produced it.

## Layout

| Path | What it is |
|---|---|
| `replay/` | The engine and the `crp` CLI: conditions, browser and evidence, twin, fixer, guard, pull requests, MCP server |
| `server/` | The service: projects, widget intake, GitHub integration, `widget.js` |
| `dashboard/` | The web dashboard (React, Vite, Tailwind) |
| `badshop/` | A small shop with planted bugs, used by tests and the demo |
| `benchmarks/` | Measured results and the data behind them |
| `scripts/` | Benchmarks, the demo exporter, training scripts |
