"""The app map: explore navigation once, then the twin goes straight to any screen (big apps made the twin wander)."""

import asyncio

from replay.agent import replay
from replay.appmap import build_map
from replay.conditions import CONDITIONS
from replay.project import running_app

PAGES = {
    "index.html": '<nav><a href="accounts.html">Accounts</a> <a href="reports.html">Reports</a></nav><h1>Budget</h1>'
                  '<button onclick="location.href=\'deleted.html\'">Delete everything</button>',
    "accounts.html": '<nav><a href="index.html">Budget</a></nav><h1>Accounts</h1>'
                     '<ul><li><a href="bank.html">Bank of America</a></li></ul>',
    "bank.html": '<h1>Bank of America</h1><button>Add transaction</button><table><tr><td>Kroger</td></tr></table>',
    "reports.html": "<h1>Reports</h1>",
    "deleted.html": "<h1>Everything deleted</h1>",
}


def app(tmp_path):
    for name, body in PAGES.items():
        (tmp_path / name).write_text(f"<!doctype html><html><body>{body}</body></html>", encoding="utf-8")
    return tmp_path


def test_the_map_finds_every_screen_by_its_path_and_never_clicks_danger(tmp_path) -> None:
    with running_app(app(tmp_path)) as url:
        screens = asyncio.run(build_map(url, CONDITIONS["fast_desktop"]))
    by_title = {s["title"]: s for s in screens}
    assert by_title["Bank of America"]["path"] == ["Accounts", "Bank of America"]
    assert "Add transaction" in by_title["Bank of America"]["controls"]
    assert "Reports" in by_title and "Everything deleted" not in by_title


def test_the_twin_goes_straight_to_a_mapped_screen_in_one_step(tmp_path) -> None:
    seen = []

    async def policy(ctx: dict) -> dict:
        seen.append(ctx["obs"]["url"])
        if len(seen) == 1:
            bank = next(s for s in ctx["app_map"] if s["title"] == "Bank of America")
            return {"type": "go", "screen": bank["id"]}
        return {"type": "verdict", "verdict": "not_reproduced"}

    with running_app(app(tmp_path)) as url:
        cond = CONDITIONS["fast_desktop"]
        screens = asyncio.run(build_map(url, cond))
        result = asyncio.run(replay(url, "x", cond, policy, app_map=screens))
    assert seen[-1].endswith("bank.html")
    assert [s["action"]["type"] for s in result.steps] == ["goto", "click", "click"]  # guards replay real steps
    assert [s["target"] for s in result.steps[1:]] == ["Accounts", "Bank of America"]
