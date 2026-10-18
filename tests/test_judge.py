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


def test_twin_sees_a_few_items_per_kind_of_evidence() -> None:
    from replay.agent import evidence_brief

    items = [Evidence(f"E{i}", "slow_request", f"GET /{i} took 12 s", 0) for i in range(25)]
    items.append(Evidence("E99", "typed_value_lost", "'Amount' held '100'", 3))
    brief = evidence_brief(items)
    assert brief.count("slow_request") == 4 and "(+22 more slow_request)" in brief and "E99" in brief


def test_load_speed_evidence_is_dropped_unless_the_complaint_is_about_speed() -> None:
    import asyncio

    from replay.llm import llm_matcher

    seen = []

    async def fake_chat(messages: list[dict]) -> str:
        system = messages[0]["content"]
        if "about speed" in system or "about_speed" in system:
            return '{"about_speed": false}'
        seen.append(messages[1]["content"])
        return '{"evidence": ["E1"], "summary": "s"}'

    slow = [Evidence("E1", "slow_page", "main content appeared after 28.6 s", 1)]
    result = asyncio.run(llm_matcher(fake_chat)("The calendar never opens", slow))
    assert result == {"evidence": []} and not seen  # the judge never even sees it


def test_a_control_tapped_again_and_again_gets_a_note() -> None:
    from replay.agent import revisit_note

    open_it = {"action": {"type": "click", "target": 4}, "result": "ok", "target": "Upcoming Utilities"}
    close = {"action": {"type": "click", "target": 9}, "result": "ok", "target": "Close"}
    assert revisit_note([open_it, close, open_it]) == ""
    assert "tapped 'Upcoming Utilities' 3 times" in revisit_note([open_it, close, open_it, close, open_it])


def test_the_twins_own_reproduced_claim_goes_through_the_judge(tmp_path) -> None:
    import asyncio

    from replay.agent import replay
    from replay.conditions import CONDITIONS
    from replay.project import running_app

    (tmp_path / "index.html").write_text("<button>Pay</button><img src=missing.png alt=x>", encoding="utf-8")  # E1

    asked = []

    async def policy(ctx: dict) -> dict:
        asked.append(ctx["last_result"])
        return {"type": "verdict", "verdict": "reproduced", "evidence": ["E1"], "summary": "slow"}

    async def strict_judge(complaint: str, evidence: list) -> dict:
        return {"evidence": []}

    with running_app(tmp_path) as url:
        result = asyncio.run(replay(url, "Pay does nothing", CONDITIONS["fast_desktop"], policy, strict_judge))
    assert result.verdict == "not_reproduced"
    # Cloud case 8926 (run 14): a refused claim ended the replay after 3 of 25 steps. It now sends the twin back once.
    assert len(asked) == 2 and asked[1].startswith("not accepted")


def test_the_twin_is_refused_a_sixth_tap_on_the_same_control(tmp_path) -> None:
    import asyncio

    from replay.agent import replay
    from replay.conditions import CONDITIONS
    from replay.project import running_app

    (tmp_path / "index.html").write_text("<button onclick=\"this.dataset.n=(+this.dataset.n||0)+1\">Upcoming</button>"
                                         "<button>Groceries</button>", encoding="utf-8")
    results = []

    async def policy(ctx: dict) -> dict:
        results.append(ctx["last_result"])
        return {"type": "click", "target": 0} if len(results) < 8 else {"type": "verdict", "verdict": "not_reproduced"}

    with running_app(tmp_path) as url:
        asyncio.run(replay(url, "x", CONDITIONS["fast_desktop"], policy))
    assert any(r.startswith("error: not tapped. You already opened 'Upcoming' 5 times") for r in results)


def test_a_number_from_a_closed_menu_is_named_and_does_not_cost_a_step(tmp_path) -> None:
    import asyncio

    from replay.agent import replay
    from replay.conditions import CONDITIONS
    from replay.project import running_app

    # Cloud case 9107 (run 13): the twin tapped [32] from a closed menu five times, each a wasted step.
    (tmp_path / "index.html").write_text(
        "<button onclick=\"m.hidden=false\">Menu</button>"
        "<div id=m hidden><button onclick=\"m.hidden=true\">Show reconciled</button></div>", encoding="utf-8")
    results = []

    async def policy(ctx: dict) -> dict:
        results.append(ctx["last_result"])
        return [{"type": "click", "target": 0}, {"type": "click", "target": 1},
                {"type": "click", "target": 1}][len(results) - 1] if len(results) < 4 else {"type": "verdict"}

    with running_app(tmp_path) as url:
        result = asyncio.run(replay(url, "x", CONDITIONS["fast_desktop"], policy))
    assert "'Show reconciled'" in results[3] and "Menu" in results[3]
    assert len(result.steps) == 2


def test_a_screen_reader_replay_keeps_what_the_user_heard(tmp_path) -> None:
    import asyncio

    from replay.agent import replay, spoken
    from replay.conditions import CONDITIONS
    from replay.project import running_app

    (tmp_path / "index.html").write_text('<h2>Cart</h2><button>1</button><img src="x.png"><a href="/">Home</a>'
                                         '<ul><li>Apples $3</li></ul><label>Qty <input value=2></label>', encoding="utf-8")

    async def policy(ctx: dict) -> dict:
        return {"type": "verdict", "verdict": "not_reproduced"}

    with running_app(tmp_path) as url:
        heard = asyncio.run(replay(url, "x", CONDITIONS["screen_reader"], policy)).heard
    assert list(heard) == ["Cart, heading level 2", "1, button", "image", "Home, link", "Apples $3", "Qty", "Qty, edit, 2"]
    assert spoken('- checkbox "Gift" [checked]\n- button "Pay" [disabled]') == ["Gift, check box, checked",
                                                                              "Pay, button, unavailable"]
    assert spoken('- button "Add Chai": Add') == ["Add Chai, button"]  # its own text is not a value
    assert asyncio.run(_sighted(tmp_path, policy)) == ()


async def _sighted(root, policy) -> list:
    from replay.agent import replay
    from replay.conditions import CONDITIONS
    from replay.project import running_app

    with running_app(root) as url:
        return (await replay(url, "x", CONDITIONS["fast_desktop"], policy)).heard


def test_the_twin_is_told_whether_a_tapped_box_is_now_ticked(tmp_path) -> None:
    import asyncio

    from replay.agent import replay
    from replay.conditions import CONDITIONS
    from replay.project import running_app

    # Cloud case 8765 (run 13): Actual's row box shows "selected" only as a checkmark SVG, and every tap said just
    # "ok", so the twin ticked and unticked the same row eight times.
    (tmp_path / "index.html").write_text(
        '<div tabindex="0" style="width:12px;height:12px;border:1px solid" '
        'onclick="this.innerHTML = this.innerHTML ? \'\' : \'<svg width=6 height=6></svg>\'"></div>'
        '<input type="checkbox" aria-label="Gift">', encoding="utf-8")
    results = []

    async def policy(ctx: dict) -> dict:
        results.append(ctx["last_result"])
        script = [{"type": "click", "target": 0}, {"type": "click", "target": 0}, {"type": "click", "target": 1}]
        return script[len(results) - 1] if len(results) <= len(script) else {"type": "verdict"}

    with running_app(tmp_path) as url:
        asyncio.run(replay(url, "x", CONDITIONS["fast_desktop"], policy))
    assert "nothing visible changed" not in results[1]
    assert "now shows a mark" in results[1] and "mark went away" in results[2] and "now checked" in results[3]


def test_a_tap_behind_an_open_menu_is_told_the_menus_own_controls(tmp_path) -> None:
    import asyncio

    from replay.agent import replay
    from replay.conditions import CONDITIONS
    from replay.project import running_app

    # Cloud case 9107 (run 14): eleven taps behind an open menu, each told only "use its controls (marked (new))";
    # the menu had opened before, so nothing in it was new.
    (tmp_path / "index.html").write_text(
        '<button>Close</button><div role="dialog" style="position:fixed;inset:0;background:#fff">'
        '<button>Hide reconciled transactions</button></div>', encoding="utf-8")
    results = []

    async def policy(ctx: dict) -> dict:
        results.append(ctx["last_result"])
        return {"type": "click", "target": 0} if len(results) == 1 else {"type": "verdict"}

    with running_app(tmp_path) as url:
        asyncio.run(replay(url, "x", CONDITIONS["fast_desktop"], policy))
    assert "[1] Hide reconciled transactions" in results[1] and "Escape" in results[1]


def test_a_link_that_opened_an_outside_tab_is_not_tapped_again(tmp_path) -> None:
    import asyncio

    from replay.agent import replay
    from replay.conditions import CONDITIONS
    from replay.project import running_app

    # Cloud case 9038 (run 15): five taps on a docs link, each opening the same page in a new tab.
    (tmp_path / "index.html").write_text('<a href="/docs.html" target="_blank">guided tour</a><button>Start</button>',
                                         encoding="utf-8")
    (tmp_path / "docs.html").write_text("docs", encoding="utf-8")
    results = []

    async def policy(ctx: dict) -> dict:
        results.append(ctx["last_result"])
        return {"type": "click", "target": 0} if len(results) <= 2 else {"type": "verdict"}

    with running_app(tmp_path) as url:
        result = asyncio.run(replay(url, "x", CONDITIONS["fast_desktop"], policy))
    assert "opened a new tab" in results[1] and results[2].startswith("error: not tapped") and len(result.steps) == 1
