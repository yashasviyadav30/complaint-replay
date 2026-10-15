from replay.conditions import CONDITIONS, Condition
from replay.guard import build_guard

STEPS = [
    {"action": {"type": "fill", "target": 0, "text": "9876543210", "why": "x"}, "result": "ok", "target": "Mobile number"},
    {"action": {"type": "click", "target": 7}, "result": "error: Timeout 5000ms exceeded.", "target": "Ghost"},
    {"action": {"type": "click", "target": 1}, "result": "ok (nothing visible changed)", "target": "Send OTP"},
    {"action": {"type": "wait", "ms": 3000}, "result": "ok", "target": None},
    {"action": {"type": "click_role", "role": "button", "name": "Cart"}, "result": "ok", "target": "Cart"},
    {"action": {"type": "click", "target": 5, "times": 2}, "result": "ok", "target": "Pay now"},
]


def test_guard_keeps_working_steps_by_name_and_drops_failures() -> None:
    guard = build_guard("c1", "complaint", CONDITIONS["slow_3g_android"], STEPS, {"request_failed"})
    assert guard["steps"] == [
        {"do": "fill", "label": "Mobile number", "text": "9876543210"},
        {"do": "click", "label": "Send OTP"},
        {"do": "wait", "ms": 3000},
        {"do": "click_role", "role": "button", "name": "Cart"},
        {"do": "click", "label": "Pay now", "times": 2},
    ]
    assert guard["must_not_see"] == ["request_failed"]


def test_guard_keeps_keyboard_steps() -> None:
    steps = [{"action": {"type": "press", "key": "Tab"}, "result": "ok"},
             {"action": {"type": "type", "text": "hello"}, "result": "ok"}]
    guard = build_guard("c1", "x", CONDITIONS["keyboard"], steps, set())
    assert guard["steps"] == [{"do": "press", "key": "Tab"}, {"do": "type", "text": "hello"}]


def test_evidence_key_ignores_numbers_but_not_the_control() -> None:
    from replay.browser import evidence_key

    a = evidence_key("offscreen_control", "'Pay' is outside the screen (left=400px, screen=360px)")
    assert a == evidence_key("offscreen_control", "'Pay' is outside the screen (left=412px, screen=360px)")
    assert evidence_key("unclear_name", "announced only as '1'") != evidence_key("unclear_name", "announced only as '+'")


def test_guard_condition_round_trips() -> None:
    guard = build_guard("c1", "complaint", CONDITIONS["slow_3g_android"], [], set())
    assert Condition(**guard["condition"]) == CONDITIONS["slow_3g_android"]
