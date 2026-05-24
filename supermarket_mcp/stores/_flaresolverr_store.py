"""
Shared session lifecycle for stores fetched through FlareSolverr per request.

Some sites can't be scraped with reused cookies: Tesco validates Akamai sensor
data on every request, and Lidl renders its product grid with JavaScript. Both
need FlareSolverr (a real browser) for every search rather than a cookie-reuse
fast path. A single FlareSolverr session is opened on first use and reused for
every solve, then destroyed on close. Subclasses supply the search-URL builder
and the results parser.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio

from supermarket_mcp import flaresolverr


class FlareSolverrStore(ABC):
    """A store that fetches every results page through FlareSolverr."""

    def __init__(self, *, name: str) -> None:
        """
        Create the store with no FlareSolverr session yet.

        Args:
            name: Store key, also used as the FlareSolverr session name.
        """

        self.name = name
        self._session_name = name
        self._ready = False
        self._lock = asyncio.Lock()

    @abstractmethod
    def _build_search_url(self, query: str) -> str:
        """Return the results-page URL for a query."""

    @abstractmethod
    def _parse(self, html: str) -> list[dict]:
        """Parse product dicts out of a results page, in site order."""

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search the store for a query and return up to limit candidates."""

        await self._ensure_session()

        return await asyncio.to_thread(self._search_sync, query, limit)

    async def close(self) -> None:
        """Destroy the FlareSolverr session backing this store."""

        if self._ready:
            await asyncio.to_thread(flaresolverr.destroy_session, self._session_name)
            self._ready = False

    async def _ensure_session(self) -> None:
        """Create the FlareSolverr session on first use."""

        async with self._lock:
            if not self._ready:
                await asyncio.to_thread(self._create)
                self._ready = True

    def _create(self) -> None:
        """Open the FlareSolverr session, clearing any stale one of the name."""

        if self._session_name in flaresolverr.list_sessions():
            flaresolverr.destroy_session(self._session_name)
        flaresolverr.create_session(self._session_name)

    def _search_sync(self, query: str, limit: int) -> list[dict]:
        """
        Fetch the results page through FlareSolverr and parse it.

        Raises:
            RuntimeError: If FlareSolverr returns a block / challenge page.
        """

        url = self._build_search_url(query)
        html, _, _ = flaresolverr.solve(self._session_name, url)
        if flaresolverr.is_blocked_page(html):
            raise RuntimeError(f"{self.name} blocked/challenge page detected: {url}")

        return self._parse(html)[:limit]
