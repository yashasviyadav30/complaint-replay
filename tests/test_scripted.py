"""Each planted bug must leave machine evidence under its condition, and the clean shop must not.

No model is involved: fixed scripts drive the browser. This proves the bug library and the
evidence detectors work before any Nemotron call.
"""

import asyncio

import pytest

from replay.agent import replay, scripted_policy
from replay.bugs import BUGS_BY_ID, inject, reset_workspace
from replay.conditions import CONDITIONS
from replay.shop import running_shop

LOGIN = [
    {"type": "fill_css", "selector": "#phone", "text": "9876543210"},
    {"type": "click_css", "selector": "#send-otp"},
    {"type": "fill_css", "selector": "#otp", "text": "123456"},
    {"type": "click_css", "selector": "#verify-otp"},
]
ADD_ITEM = {"type": "click_css", "selector": "#products button"}
OPEN_CART = {"type": "click_css", "selector": "#cart-btn"}

# bug id -> (script, evidence kind that must appear only when the bug is present)
CASES = {
    1: (LOGIN[:2], "request_failed"),
    4: ([*LOGIN, ADD_ITEM, OPEN_CART], "offscreen_control"),
    7: ([*LOGIN[:2], {"type": "fill_css", "selector": "#otp", "text": "000000"},
         {"type": "click_css", "selector": "#verify-otp"}], "language_mismatch"),
    10: ([*LOGIN, ADD_ITEM], "a11y_violation"),
    15: ([*LOGIN, ADD_ITEM, OPEN_CART, {"type": "fill_css", "selector": "#coupon", "text": "SAVE10"},
          {"type": "click_css", "selector": "#apply-coupon"}, {"type": "click_css", "selector": "#pay"}],
         "amount_mismatch"),
}


def evidence_kinds(bug_id: int, buggy: bool, condition: str | None = None) -> set[str]:
    bug = BUGS_BY_ID[bug_id]
    script, _ = CASES[bug_id]
    shop = reset_workspace()
    if buggy:
        inject(bug, shop)
    cond = CONDITIONS[condition or bug.condition]
    with running_shop(shop) as url:
        result = asyncio.run(replay(url, bug.complaint, cond, scripted_policy(script)))
    return {e.kind for e in result.evidence}


@pytest.mark.parametrize("bug_id", sorted(CASES))
def test_bug_leaves_evidence_only_when_present(bug_id: int) -> None:
    _, kind = CASES[bug_id]
    assert kind in evidence_kinds(bug_id, buggy=True)
    assert kind not in evidence_kinds(bug_id, buggy=False)


def test_otp_bug_works_for_me_on_a_fast_laptop() -> None:
    """The whole point: the developer's machine hides bugs that real users hit."""
    assert "request_failed" not in evidence_kinds(1, buggy=True, condition="fast_desktop")
