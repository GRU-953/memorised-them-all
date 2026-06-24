"""Verify the MCP server starts over stdio and registers all eight tools.

Used by CI as a lightweight integration check. Requires the ``mcp`` package.
Runs with Ollama disabled so it never touches the network.
"""
from __future__ import annotations

import asyncio
import os
import sys

EXPECTED = {"digest", "convert", "recall", "memory_overview", "export_memory",
            "list_digestible", "memory_status", "forget",
            "diff_memory", "import_memory", "merge_memory"}


async def _main() -> int:
    os.environ["MTA_NO_OLLAMA"] = "1"
    os.environ["MTA_AUTO_UPDATE"] = "off"
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "mta.server"],
                                   env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
    missing = EXPECTED - names
    if missing:
        print(f"FAIL — missing tools: {missing}", file=sys.stderr)
        return 1
    print(f"OK — {len(names)} tools registered: {sorted(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
