"""
Supermarket MCP server.

Exposes grocery search across multiple Irish supermarkets (Dunnes, SuperValu,
Aldi, Tesco, Lidl) as MCP tools. Each store owns its own FlareSolverr-backed
session lifecycle. The tools dispatch on a store argument.

Usage:
    uv run supermarket-mcp                                  # stdio (default)
    MCP_TRANSPORT=streamable-http uv run supermarket-mcp    # HTTP on MCP_PORT

Configuration:
    FLARESOLVERR_URL: FlareSolverr endpoint (default http://127.0.0.1:8191/v1).
    MCP_TRANSPORT: "stdio" (default) or "streamable-http".
    MCP_HOST: HTTP bind host (default 127.0.0.1). Used by streamable-http.
    MCP_PORT: HTTP bind port (default 8765). Used by streamable-http.
    MCP_SESSION_TTL: Cookie-reuse store session lifetime in seconds before
        recycling (3600). Applies to Dunnes, SuperValu, and Aldi.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import TYPE_CHECKING, Literal, cast

from mcp.server.fastmcp import FastMCP

from supermarket_mcp.stores.aldi import AldiStore
from supermarket_mcp.stores.dunnes import DunnesStore
from supermarket_mcp.stores.lidl import LidlStore
from supermarket_mcp.stores.supervalu import SuperValuStore
from supermarket_mcp.stores.tesco import TescoStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from supermarket_mcp.stores.base import Store

TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_PORT", "8765"))
SESSION_TTL_SECONDS = float(os.getenv("MCP_SESSION_TTL", "3600"))

STORES: dict[str, Store] = {
    "dunnes": DunnesStore(ttl_seconds=SESSION_TTL_SECONDS),
    "supervalu": SuperValuStore(ttl_seconds=SESSION_TTL_SECONDS),
    "aldi": AldiStore(ttl_seconds=SESSION_TTL_SECONDS),
    "tesco": TescoStore(),
    "lidl": LidlStore(),
}


def _get_store(name: str) -> Store:
    """
    Look up a store backend by name.

    Args:
        name: Store key, one of STORES.

    Returns:
        The matching Store.

    Raises:
        ValueError: If name is not a known store.
    """

    store = STORES.get(name)
    if store is None:
        raise ValueError(f"Unknown store {name!r}. Choose from {sorted(STORES)}")

    return store


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Close every store's FlareSolverr session on graceful shutdown."""

    try:
        yield
    finally:
        for store in STORES.values():
            await store.close()


mcp = FastMCP("supermarket", lifespan=_lifespan, host=HOST, port=PORT)


@mcp.tool()
async def search_product(query: str, store: str = "dunnes", limit: int = 10) -> dict:
    """
    Search a supermarket for a single product.

    Returns candidates in the store's own relevance order. The caller picks the
    right one. No silent best-match is chosen.

    Args:
        query: Free-text product search, e.g. "Avonmore Fresh Milk 2L".
        store: Which store: "dunnes", "supervalu", "aldi", "tesco", or "lidl".
        limit: Maximum number of candidates to return.

    Returns:
        A dict with the query, store, whether anything was found, and the
        candidate list (name, price, was, discount, unit_price, available, url).
    """

    candidates = await _get_store(store).search(query, limit)

    return {
        "query": query,
        "store": store,
        "found": bool(candidates),
        "candidates": candidates,
    }


@mcp.tool()
async def build_shopping_list(
    queries: list[str], store: str = "dunnes", limit: int = 10
) -> list[dict]:
    """
    Search several products at once and return candidates per item.

    Runs each query through search_product against the same store and collects
    the results in order. The caller selects one candidate per item.

    Args:
        queries: Product search strings, one per shopping-list item.
        store: Which store: "dunnes", "supervalu", "aldi", "tesco", or "lidl".
        limit: Maximum number of candidates to return per query.

    Returns:
        A list of per-query dicts (query, store, found, candidates), in order.
    """

    return [await search_product(query, store, limit) for query in queries]


def main() -> None:
    """Run the MCP server over the configured transport (MCP_TRANSPORT)."""

    mcp.run(transport=cast("Literal['stdio', 'sse', 'streamable-http']", TRANSPORT))


if __name__ == "__main__":
    main()
