"""
Smoke-test the supermarket MCP server over a real stdio round-trip.

Spawns the server as a subprocess, lists its tools, and calls search_product,
printing the result. This hits FlareSolverr, so run it from a host that shares
the FlareSolverr egress IP.

Usage:
    uv run python scripts/smoke.py [query] [--store dunnes|supervalu|aldi|tesco|lidl] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from supermarket_mcp.server import STORES


async def smoke(query: str, store: str, limit: int) -> None:
    """Connect over stdio, list tools, and call search_product once."""

    params = StdioServerParameters(
        command="uv", args=["run", "supermarket-mcp"], env=dict(os.environ)
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        print("tools:", [t.name for t in tools.tools])
        result = await session.call_tool(
            "search_product", {"query": query, "store": store, "limit": limit}
        )
        if result.structuredContent is not None:
            print(json.dumps(result.structuredContent, indent=2, ensure_ascii=False))
            return
        first = result.content[0] if result.content else None
        if not isinstance(first, TextContent):
            print(result.content)
            return
        try:
            payload = json.loads(first.text)
        except json.JSONDecodeError:
            print(first.text)
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    """Parse the optional query/store/limit arguments and run the round-trip."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="milk")
    parser.add_argument("--store", default="dunnes", choices=sorted(STORES))
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(smoke(args.query, args.store, args.limit))


if __name__ == "__main__":
    main()
