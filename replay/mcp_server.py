"""MCP server: coding agents (Claude Code, Cursor, Copilot) replay complaints and run guards themselves.

    claude mcp add complaint-replay -- crp mcp        (from the app's repo; needs `complaint-replay[mcp]`)

An agent that picked up a "replay could not fix this" issue can reproduce the bug as the user, change the code,
and run the guard (the issue's acceptance test) until it passes, without a person in between.
"""

import asyncio
import contextlib
import io
import json
from pathlib import Path

from mcp.server import MCPServer

from replay import cli

mcp = MCPServer("Complaint Replay")
REPO = Path.cwd()
_one_at_a_time = asyncio.Lock()  # replays share the browser, the app's port and the printed output


async def _captured(argv: list[str], command) -> tuple[int, str]:
    """Run a crp command, returning what it printed instead of writing it to stdout (stdout is the protocol)."""
    out = io.StringIO()
    async with _one_at_a_time:
        with contextlib.redirect_stdout(out):
            code = await command(cli.parser().parse_args(argv))
    return code, out.getvalue()


@mcp.tool()
async def replay_complaint(complaint: str, user: str = "", device: str = "", network: str = "wifi", url: str = "",
                           fix: bool = False) -> str:
    """Replay a user's complaint in a real browser, as that user, and report what broke.

    user: a ready-made user, one of the names in `crp replay --help` (e.g. screen_reader, keyboard, hindi).
    device: a phone or computer name (see find_devices); network: wifi, 4g, 3g, slow_3g, ...
    url: a running site to replay; empty starts the app from complaint-replay.toml.
    fix: also write a fix, prove it with the same steps, and save a guard test (no pull request).
    Takes a few minutes. Returns the verdict, the machine evidence ("*" marks the proof), and the case file,
    which holds every step and the film (a captioned GIF of the steps).
    """
    argv = ["replay", complaint, "--repo", str(REPO), "--network", network]
    argv += [f"--user={user}"] * bool(user) + [f"--device={device}"] * bool(device) + [f"--url={url}"] * bool(url)
    argv += ["--fix"] * fix
    try:
        _, text = await _captured(argv, cli.cmd_replay)
    except SystemExit:  # argparse rejected a value: say which ones are allowed
        return f"error: unknown user or network. Users: {', '.join(sorted(cli.CONDITIONS))}. Networks: {', '.join(cli.NETWORKS)}"
    runs = sorted((REPO / cli.RUNS).glob("*.json"), key=lambda p: p.stat().st_mtime)
    return text + (f"\nCase file: {runs[-1]}" if runs else "")


@mcp.tool()
async def run_guards(url: str = "") -> str:
    """Run every guard test in .complaint-replay/guards against the app: each replays a fixed bug's exact steps.

    Use it after changing code: FAIL means a user's bug is back. url: a running site; empty starts the app.
    """
    code, text = await _captured(["guard", "--repo", str(REPO)] + [f"--url={url}"] * bool(url), cli.cmd_guard)
    return text + ("\nAll guards pass." if code == 0 else "\nSome guards fail.")


@mcp.tool()
def find_devices(name: str = "") -> str:
    """List device profiles (screen size, touch, user agent) whose name contains `name`, e.g. 'galaxy', 'iphone'."""
    found = {k: v for k, v in cli.devices().items() if name.lower() in k.lower()}
    return json.dumps(sorted(found)[:60])


def serve(repo: str = ".") -> None:
    global REPO
    REPO = Path(repo).resolve()
    mcp.run()
