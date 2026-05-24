"""The Store interface shared by every supermarket scraper."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Store(Protocol):
    """
    A searchable supermarket backend.

    Implementations own their own session lifecycle (FlareSolverr sessions,
    cookies, TTLs) behind these two methods. search returns product dicts in the
    shape produced by helpers.product, in the site's own relevance order.
    """

    name: str

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Return up to limit candidate products for a free-text query."""
        ...

    async def close(self) -> None:
        """Release any session held by the store (called on server shutdown)."""
        ...
