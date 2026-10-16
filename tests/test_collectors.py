"""Each evidence collector fires on a page that has its problem, and stays silent on a clean page.

Real browser, no model. Pages live in tests/pages and are served as a plain static site.
"""

import asyncio
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
]
# The same problem fixed: these must stay silent.
CLEAN = [
    ("clean.html", PHONE, []),
    ("clean.html", CONDITIONS["keyboard"], [TAB]),
    ("clean.html", profile(network="flaky"), []),
    ("rtl_ok.html", CONDITIONS["arabic"], []),
    ("spanish_ok.html", profile(locale="es-ES"), []),
    ("modal_open.html", PHONE, []),  # an open dialog is meant to cover the page
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
