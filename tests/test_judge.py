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


def test_policy_accepts_bare_action_and_never_lets_garbage_decide() -> None:
    import asyncio

    from replay.conditions import CONDITIONS
    from replay.llm import llm_policy

    replies = iter(['{"type": "click", "target": 2}', "no json", "still none", "nope"])

    async def fake_chat(_messages: list[dict]) -> str:
        return next(replies)

    ctx = {"complaint": "x", "condition": CONDITIONS["fast_desktop"], "step": 0, "evidence": [], "steps": [],
           "last_result": "ok", "obs": {"elements": [], "text": "", "offscreen": [], "alerts": []}}
    policy = llm_policy(fake_chat)
    assert asyncio.run(policy(ctx))["type"] == "click"
    assert asyncio.run(policy(ctx))["type"] == "wait"


def test_parse_json_takes_first_object_when_model_sends_two() -> None:
    reply = '{"action": {"type": "click", "target": 1}} {"action": {"type": "wait"}}'
    assert parse_json(reply)["action"] == {"type": "click", "target": 1}


def test_model_reply_with_raw_line_breaks_in_a_string_still_parses() -> None:
    from replay.llm import parse_json

    reply = '{"explanation": "x", "edits": [{"file": "a.js", "find": "if (a) {\n  b()\n}", "replace": "c"}]}'
    assert parse_json(reply)["edits"][0]["find"].startswith("if (a)")


def test_skeptic_drops_obstacles_the_judge_cited() -> None:
    import asyncio

    from replay.browser import Evidence
    from replay.llm import llm_matcher

    switch = Evidence("E1", "no_response", "tapped 'Reconciled' but nothing happened", 3)
    obstacle = Evidence("E2", "tap_blocked", "tapping 'Upcoming Utilities' hit <div> instead", 2)
    replies = iter(['{"evidence": ["E1", "E2"], "summary": "s"}', '{"answer": "problem"}', '{"answer": "other"}'])

    async def chat(messages):
        return next(replies)

    result = asyncio.run(llm_matcher(chat)("The Reconciled switch does nothing", [switch, obstacle]))
    assert result["evidence"] == ["E1"]


def test_twin_sees_what_each_past_click_hit() -> None:
    from replay.agent import build_prompt
    from replay.conditions import profile

    steps = [{"action": {"type": "click", "target": 5, "why": "open a transaction"}, "result": "ok",
              "target": "Previous month"}]
    ctx = {"condition": profile("Pixel 7"), "obs": {"elements": [], "text": ""}, "evidence": [], "steps": steps,
           "complaint": "c", "step": 1, "last_result": "ok"}
    _, user = build_prompt(ctx)
    assert '{"type": "click", "target": 5} on \'Previous month\' -> ok' in user
