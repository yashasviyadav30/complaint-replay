"""Research step: Tavily finds the documented cause of the evidence, so the fix can cite a real source.

Optional by design: with no TAVILY_API_KEY, or if the search fails, the fix still runs, just without sources.
"""

import asyncio
import json
import logging
import os
import urllib.request
from collections.abc import Callable

from replay.browser import Evidence

TAVILY_URL = "https://api.tavily.com/search"
MAX_SOURCES = 3
log = logging.getLogger("complaint-replay")

# What a developer would search for, per kind of machine evidence.
QUERIES = {
    "request_failed": "fetch request aborted by timeout on slow mobile network, how to fix",
    "offscreen_control": "CSS flex row pushes button off screen on small mobile viewport, how to fix",
    "language_mismatch": "hard-coded English error message shown in a localized app, i18n fix",
    "amount_mismatch": "checkout charges full price although the cart shows the coupon discount, bug cause",
    "duplicate_request": "prevent double submit of payment button, duplicate order on slow network",
}
Post = Callable[[str, dict, str], dict]


def research_query(evidence: Evidence) -> str:
    if evidence.kind == "a11y_violation":  # detail starts with the axe rule id, e.g. "button-name: ..."
        return f"axe-core rule {evidence.detail.split(':', 1)[0]} how to fix"
    return QUERIES.get(evidence.kind, f"{evidence.detail[:150]} how to fix")


def _post(url: str, body: dict, key: str) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


async def research(evidence: list[Evidence], post: Post = _post) -> list[dict]:
    key = os.getenv("TAVILY_API_KEY")
    if not key or not evidence:
        return []
    body = {"query": research_query(evidence[0]), "max_results": MAX_SOURCES, "search_depth": "basic"}
    try:
        results = (await asyncio.to_thread(post, TAVILY_URL, body, key)).get("results", [])
    except (OSError, ValueError) as e:  # HTTP errors are OSError; research must never block a fix
        log.warning("Tavily search failed: %s", e)
        return []
    return [{"title": str(r.get("title", ""))[:200], "url": str(r.get("url", "")), "content": str(r.get("content", ""))[:600]}
            for r in results[:MAX_SOURCES] if r.get("url")]
