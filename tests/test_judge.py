from replay.agent import judge
from replay.browser import Evidence
from replay.llm import parse_json

EV = [Evidence("E1", "request_failed", "POST /api/otp/send failed", 2)]


def test_reproduced_without_real_evidence_is_downgraded() -> None:
    result = judge({"verdict": "reproduced", "evidence": ["E9"], "summary": "trust me"}, EV, [])
    assert result.verdict == "not_reproduced"
    assert "Downgraded" in result.summary


def test_reproduced_with_real_evidence_stands() -> None:
    result = judge({"verdict": "reproduced", "evidence": ["E1"], "summary": "OTP timed out"}, EV, [])
    assert result.verdict == "reproduced"
    assert result.cited == ("E1",)


def test_unknown_verdict_becomes_not_reproduced() -> None:
    assert judge({"verdict": "maybe"}, EV, []).verdict == "not_reproduced"


def test_parse_json_ignores_reasoning_and_prose() -> None:
    reply = '<think>{"not": "this"}</think>Sure! {"thought": "x", "action": {"type": "wait", "ms": 500}} done'
    assert parse_json(reply)["action"] == {"type": "wait", "ms": 500}
