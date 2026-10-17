"""The MCP server as a coding agent meets it: a subprocess speaking the protocol on stdin/stdout."""

import asyncio
import sys

from mcp import Client, StdioServerParameters


def test_a_coding_agent_lists_the_tools_and_gets_printed_output_back_not_on_the_wire(tmp_path) -> None:
    async def talk() -> tuple[set, str, str]:
        server = StdioServerParameters(command=sys.executable, args=["-m", "replay.cli", "mcp", "--repo", str(tmp_path)])
        async with Client(server) as agent:
            names = {t.name for t in (await agent.list_tools()).tools}
            devices = (await agent.call_tool("find_devices", {"name": "pixel 7"})).content[0].text
            # `crp guard` prints; if that went to stdout, the protocol stream would break before this returns.
            guards = (await agent.call_tool("run_guards", {})).content[0].text
        return names, devices, guards

    names, devices, guards = asyncio.run(talk())
    assert names == {"replay_complaint", "run_guards", "find_devices"}
    assert "Pixel 7" in devices
    assert "No guard tests" in guards and "All guards pass." in guards
