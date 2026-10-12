from replay.conditions import CONDITIONS, Condition
from replay.guard import build_guard

STEPS = [
    {"action": {"type": "fill", "target": 0, "text": "9876543210", "why": "x"}, "result": "ok", "target": "Mobile number"},
    {"action": {"type": "click", "target": 7}, "result": "error: Timeout 5000ms exceeded.", "target": "Ghost"},
    {"action": {"type": "click", "target": 1}, "result": "ok (nothing visible changed)", "target": "Send OTP"},
    {"action": {"type": "wait", "ms": 3000}, "result": "ok", "target": None},
    {"action": {"type": "click_role", "role": "button", "name": "Cart"}, "result": "ok", "target": "Cart"},
]


def test_guard_keeps_working_steps_by_name_and_drops_failures() -> None:
    guard = build_guard("c1", "complaint", CONDITIONS["slow_3g_android"], STEPS, {"request_failed"})
    assert guard["steps"] == [
        {"do": "fill", "label": "Mobile number", "text": "9876543210"},
        {"do": "click", "label": "Send OTP"},
        {"do": "wait", "ms": 3000},
        {"do": "click_role", "role": "button", "name": "Cart"},
    ]
    assert guard["must_not_see"] == ["request_failed"]


def test_guard_condition_round_trips() -> None:
    guard = build_guard("c1", "complaint", CONDITIONS["slow_3g_android"], [], set())
    assert Condition(**guard["condition"]) == CONDITIONS["slow_3g_android"]
