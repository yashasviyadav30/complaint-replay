import asyncio
import urllib.error

from replay.browser import Evidence
from replay.research import research, research_query

AXE = Evidence("E1", "a11y_violation", "button-name: Buttons must have discernible text (#cart-btn)", 3)
ABORT = Evidence("E1", "request_failed", "POST /api/otp/send failed (net::ERR_ABORTED)", 2)


def test_query_uses_the_axe_rule_or_the_evidence_kind() -> None:
    assert research_query(AXE) == "axe-core rule button-name how to fix"
    assert "slow mobile network" in research_query(ABORT)


def test_no_key_means_no_search(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert asyncio.run(research([AXE], post=lambda *a: 1 / 0)) == []  # would crash if it searched


def test_parses_results_and_sends_the_key(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    seen = {}

    def fake_post(url: str, body: dict, key: str) -> dict:
        seen.update(url=url, query=body["query"], key=key)
        return {"results": [
            {"title": "Button name rule", "url": "https://dequeuniversity.com/rules/axe/4.10/button-name", "content": "Ensure buttons have text"},
            {"title": "no url"},
        ]}

    sources = asyncio.run(research([AXE], post=fake_post))
    assert seen == {"url": "https://api.tavily.com/search", "query": "axe-core rule button-name how to fix", "key": "tvly-test"}
    assert [s["url"] for s in sources] == ["https://dequeuniversity.com/rules/axe/4.10/button-name"]


def test_a_failed_search_never_blocks_the_fix(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    def unauthorized(*_args) -> dict:
        raise urllib.error.HTTPError("https://api.tavily.com/search", 401, "Unauthorized", None, None)

    assert asyncio.run(research([AXE], post=unauthorized)) == []
