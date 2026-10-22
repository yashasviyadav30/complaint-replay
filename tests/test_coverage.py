"""Which code ran in the step that showed the bug: the fixer's map to the right file (Actual 8733 patched the
caller of the helper that lost the amount, run after run)."""

import asyncio
from dataclasses import replace

from replay.agent import replay, scripted_policy
from replay.conditions import CONDITIONS
from replay.fix import fix_clues
from replay.project import running_app

UTILS = "function normalizeAmount(t) { return { ...t, amount: t.debit ?? null }; }  // forgets t.amount\n"
APP = """let state = { amount: null, cleared: false };
document.getElementById("amount").oninput = (e) => { state.amount = e.target.value; };
document.getElementById("cleared").onclick = () => {
  state = normalizeAmount({ ...state, cleared: true });
  document.getElementById("amount").value = state.amount ?? "";
};
"""


def test_the_step_that_lost_the_value_names_the_helper_that_ran(tmp_path) -> None:
    (tmp_path / "utils.js").write_text(UTILS, encoding="utf-8")
    (tmp_path / "app.js").write_text(APP, encoding="utf-8")
    (tmp_path / "index.html").write_text(
        '<!doctype html><html><body><input id="amount" aria-label="Amount"><button id="cleared">Cleared</button>'
        '<script src="utils.js"></script><script src="app.js"></script></body></html>', encoding="utf-8")
    steps = [{"type": "fill_css", "selector": "#amount", "text": "42"}, {"type": "click_css", "selector": "#cleared"}]
    with running_app(tmp_path) as url:
        result = asyncio.run(replay(url, "amount disappears", CONDITIONS["fast_desktop"], scripted_policy(steps)))
    lost = next(e for e in result.evidence if e.kind == "typed_value_lost")
    assert "utils.js normalizeAmount" in result.ran[lost.step], result.ran
    assert any("normalizeAmount" in clue for clue in fix_clues(replace(result, cited=(lost.id,))))
