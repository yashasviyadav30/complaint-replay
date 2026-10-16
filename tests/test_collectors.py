"""Each evidence collector fires on a page that has its problem, and stays silent on a clean page.

Real browser, no model. Pages live in tests/pages and are served as a plain static site.
"""

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

import replay.browser as browser
from replay.agent import replay, scripted_policy
from replay.conditions import CONDITIONS, profile
from replay.project import running_app

PAGES = Path(__file__).parent / "pages"
PHONE = profile("Galaxy S9+")
TAB = {"type": "press", "key": "Tab"}

# page, condition, script, evidence kind that must appear
CASES = [
    ("overflow.html", PHONE, [], "page_overflow"),
    ("covered.html", PHONE, [], "covered_control"),
    ("clipped.html", PHONE, [], "clipped_text"),
    ("broken_image.html", CONDITIONS["fast_desktop"], [], "broken_image"),
    ("spinner.html", CONDITIONS["fast_desktop"], [{"type": "wait", "ms": 1500}], "stuck_loading"),
    ("redirect.html", CONDITIONS["fast_desktop"], [{"type": "wait", "ms": 1500}], "redirect_loop"),
    ("rtl.html", CONDITIONS["arabic"], [], "rtl_missing"),
    ("spanish.html", profile(locale="es-ES"), [], "language_mismatch"),
    ("keyboard.html", CONDITIONS["keyboard"], [TAB], "focus_invisible"),
    ("keyboard.html", CONDITIONS["keyboard"], [], "not_keyboard_reachable"),
    ("fetches.html", profile(network="flaky"), [{"type": "click_css", "selector": "button"}], "request_failed"),
    ("fetches.html", profile(network="drops"), [{"type": "click_css", "selector": "button"}], "request_failed"),
    ("shift.html", CONDITIONS["fast_desktop"], [{"type": "wait", "ms": 1200}], "layout_shift"),
    ("unnamed.html", CONDITIONS["screen_reader"], [], "unclear_name"),
    ("dead_button.html", PHONE, [{"type": "click_css", "selector": "#pick"}], "no_response"),
    ("blocked.html", PHONE, [{"type": "click_css", "selector": "#date"}], "tap_blocked"),
    ("no_label.html", replace(PHONE, audit=True), [], "a11y_violation"),  # public-sector pack: everyone audited
    ("amount.html", PHONE, [{"type": "fill_css", "selector": "#amount", "text": "42.50"},
                            {"type": "click_css", "selector": "#buggy-cleared"}], "typed_value_lost"),
]
# The same problem fixed: these must stay silent.
CLEAN = [
    ("clean.html", PHONE, []),
    ("clean.html", CONDITIONS["keyboard"], [TAB]),
    ("clean.html", profile(network="flaky"), []),
    ("rtl_ok.html", CONDITIONS["arabic"], []),
    ("spanish_ok.html", profile(locale="es-ES"), []),
    ("modal_open.html", PHONE, []),  # an open dialog is meant to cover the page
    ("chrome.html", PHONE, []),  # a fixed top bar over the list is page chrome, not a covered control
    ("amount.html", PHONE, [{"type": "fill_css", "selector": "#amount", "text": "42.50"},
                            {"type": "click_css", "selector": "#cleared"}]),  # the working toggle keeps the amount
    ("clean.html", PHONE, [{"type": "click_css", "selector": "button"}]),  # the button changes its text
    ("dead_button.html", PHONE, [{"type": "click_css", "selector": "#toggle"}]),  # a toggle that toggles
]


@pytest.fixture(scope="module")
def site():
    with running_app(PAGES) as url:
        yield url


@pytest.fixture(autouse=True)
def quick_spinner(monkeypatch):
    monkeypatch.setattr(browser, "STUCK_LOADING_S", 1)


def kinds(url: str, cond, script: list[dict]) -> list[str]:
    result = asyncio.run(replay(url, "test", cond, scripted_policy(list(script))))
    return [f"{e.kind}: {e.detail}" for e in result.evidence]


@pytest.mark.parametrize("page,cond,script,kind", CASES, ids=[f"{c[0]}-{c[3]}" for c in CASES])
def test_collector_fires(site, page, cond, script, kind) -> None:
    found = kinds(f"{site}/{page}", cond, script)
    assert any(f.startswith(kind + ":") for f in found), found


@pytest.mark.parametrize("page,cond,script", CLEAN, ids=[f"{c[0]}-{c[1].label}" for c in CLEAN])
def test_clean_page_is_silent(site, page, cond, script) -> None:
    found = kinds(f"{site}/{page}", cond, script)
    noisy = [f for f in found if not f.startswith("a11y_violation")]  # axe has opinions even about tiny pages
    assert not noisy, noisy


def test_a_teams_own_check_becomes_evidence(site) -> None:
    from replay.browser import Session

    total_check = """() => {
      const sum = [...document.querySelectorAll('.line')].reduce((s, l) => s + Number(l.dataset.amount), 0);
      const shown = Number(document.querySelector('#total').textContent);
      return sum === shown ? [] : [`total shows ${shown} but the lines add up to ${sum}`];
    }"""

    async def run() -> list[str]:
        async with Session(f"{site}/invoice.html", PHONE, checks={"invoice_total": total_check}) as s:
            await s.observe()
            return [f"{e.kind}: {e.detail}" for e in s.evidence]

    assert asyncio.run(run()) == ["check:invoice_total: total shows 160 but the lines add up to 150"]



def test_a_control_without_a_name_is_described_by_the_text_beside_it(site) -> None:
    from replay.browser import Session

    async def labels() -> list[str]:
        async with Session(f"{site}/chrome.html", PHONE) as s:
            return [e["label"] for e in (await s.observe())["elements"]]

    assert "(no name) near 'Reconciled'" in asyncio.run(labels())



def test_keyboard_choice_must_be_the_highlighted_option(site) -> None:
    from replay.browser import Session

    async def run(page: str) -> list[str]:
        async with Session(f"{site}/{page}", CONDITIONS["keyboard"]) as s:
            await s.act({"type": "press", "key": "ArrowDown"})
            await s.act({"type": "press", "key": "Enter"})
            return [e.kind for e in s.evidence]

    assert "wrong_option_chosen" in asyncio.run(run("combo.html#buggy"))
    assert "wrong_option_chosen" not in asyncio.run(run("combo.html"))


def test_twin_reloads_a_page_that_never_finishes_loading(site, monkeypatch) -> None:
    monkeypatch.setattr(browser, "READY_TEXT_TIMEOUT_S", 2)

    async def body() -> str:
        async with browser.Session(f"{site}/reload.html", PHONE, ready_text="Try the demo") as s:
            return await s.page.inner_text("body")

    assert "Try the demo" in asyncio.run(body())


def test_a_menu_covering_the_control_that_opened_it_is_not_a_blocked_tap(site) -> None:
    # Cloud case 9071: the second tap on a month picker hit its own open popover and was cited as the bug.
    taps = [{"type": "click_css", "selector": "#month"}] * 2
    assert not [k for k in kinds(f"{site}/popover.html", PHONE, taps) if k.startswith("tap_blocked")]


def test_a_made_up_control_number_gets_a_clear_error_fast(site) -> None:
    async def body() -> str:
        async with browser.Session(f"{site}/popover.html", PHONE) as s:
            await s.observe()
            return await s.act({"type": "click", "target": 999})

    assert asyncio.run(body()).startswith("error: there is no control [999]")


def test_waiting_on_a_loaded_page_says_nothing_is_loading(site) -> None:
    async def body() -> str:
        async with browser.Session(f"{site}/popover.html", PHONE) as s:
            await s.observe()
            return await s.act({"type": "wait", "ms": 100})

    assert "nothing on this screen is loading" in asyncio.run(body())


def test_controls_that_just_appeared_are_marked_new(site) -> None:
    async def body() -> list[str]:
        async with browser.Session(f"{site}/popover.html", PHONE) as s:
            obs = await s.observe()
            await s.page.evaluate("document.body.insertAdjacentHTML('beforeend', '<button>Post transaction</button>')")
            obs = await s.observe()
            return [e["label"] for e in obs["elements"] if e["new"]]

    assert asyncio.run(body()) == ["Post transaction"]


def test_a_disabled_control_is_not_evidence_and_the_twin_hears_why(site, monkeypatch) -> None:
    async def body() -> tuple[str, list]:
        async with browser.Session(f"{site}/disabled.html", PHONE) as s:
            obs = await s.observe()
            idx = next(e["idx"] for e in obs["elements"] if e["label"].startswith("Who did you pay"))
            return await s.act({"type": "click", "target": idx}), [e.kind for e in s.evidence]

    result, kinds_seen = asyncio.run(body())
    assert result.startswith("error: that control is disabled") and "tap_blocked" not in kinds_seen


def test_keyboard_twin_can_hold_tab(site) -> None:
    async def body() -> str:
        async with browser.Session(f"{site}/popover.html", PHONE) as s:
            await s.page.set_content("<button>a</button><button>b</button><button>c</button><button id=d>d</button>")
            await s.act({"type": "press", "key": "Tab", "times": 4})
            return await s.page.evaluate("document.activeElement.id")

    assert asyncio.run(body()) == "d"


def test_a_tap_behind_an_open_dialog_is_not_evidence(site) -> None:
    async def body() -> tuple[str, list]:
        async with browser.Session(f"{site}/dialog.html", PHONE) as s:
            obs = await s.observe()
            idx = next(e["idx"] for e in obs["elements"] if e["label"] == "Upcoming Utilities")
            return await s.act({"type": "click", "target": idx}), [e.kind for e in s.evidence]

    result, seen = asyncio.run(body())
    assert result.startswith("error: a dialog or menu is open") and "tap_blocked" not in seen


def test_a_key_press_says_where_the_focus_went(site) -> None:
    async def body() -> str:
        async with browser.Session(f"{site}/popover.html", PHONE) as s:
            await s.page.set_content("<button>Try the demo</button><button>Start fresh</button>")
            return await s.act({"type": "press", "key": "Tab"})

    assert asyncio.run(body()) == "ok, focus is now on button 'Try the demo'"


def test_controls_sharing_a_name_get_their_row(site) -> None:
    async def body() -> list[str]:
        async with browser.Session(f"{site}/popover.html", PHONE) as s:
            await s.page.set_content("<table><tr><td><button>✓</button></td><td>Dominion Power -120.00</td></tr>"
                                     "<tr><td><button>✓</button></td><td>Home Depot -4.72</td></tr></table>")
            return [e["label"] for e in (await s.observe())["elements"]]

    labels = asyncio.run(body())
    assert labels[0].startswith("✓ in row '") and "Dominion Power" in labels[0] and "Home Depot" in labels[1]
