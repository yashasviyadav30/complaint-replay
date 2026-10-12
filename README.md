# Complaint Replay (working name)

Turns a user's complaint into proof of the bug, a fix, and a test, by replaying it in a real browser under that user's real conditions.

Built for the Nebius x NVIDIA Global AI Hackathon with NVIDIA Nemotron models on Nebius Token Factory.

> Work in progress. The full README for judges comes later.

## What works today

- **BadShop** (`badshop/`): a small demo store (OTP login, products, cart, coupon, checkout) in FastAPI + plain JS.
- **Bug library** (`replay/bugs.py`): realistic bugs injected into a copy of BadShop, each tied to a user condition.
- **Real conditions** (`replay/conditions.py`): slow 3G + cheap Android (3 s latency, 4x CPU slowdown, 360 px screen), Hindi locale, screen reader (accessibility tree only), elderly (200% zoom, 8-step patience).
- **Machine evidence** (`replay/browser.py`): failed requests, HTTP errors, console errors, off-screen controls, English-only errors shown to Hindi users, accessibility violations (axe-core), money mismatches between API calls. The model can't add evidence; it can only cite it.
- **Replay loop** (`replay/agent.py`, `replay/llm.py`): Nemotron reads the page and picks one action at a time until it gives a verdict: `reproduced`, `ux_confusion` or `not_reproduced`.

## Run

```bash
uv sync
uv run playwright install chromium
uv run pytest -q                  # scripted checks, no API key needed
cp .env.example .env              # add NEBIUS_API_KEY
uv run python risk_test.py        # Nemotron vs 5 planted bugs
```

## License

Apache 2.0. See `LICENSE`.
