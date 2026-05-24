"""
Shared session lifecycle for stores that reuse harvested bot-protection cookies.

FlareSolverr solves the challenge once on the store homepage. The resulting
cookies + user-agent are reused with a plain requests session until they age
past the TTL, after which the next search recycles them. A page that comes back
as a challenge mid-session is re-solved transparently. Subclasses supply the
home URL, the search-URL builder, and the results parser.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import re
import time

import requests

from supermarket_mcp import flaresolverr

_PACK_MULTIPLIER = re.compile(
    r"\b\d+(?:\.\d+)?\s*[x×]\s*\d+(?:\.\d+)?\s*[a-z]*\b", re.IGNORECASE
)
_MEASUREMENT = re.compile(
    r"\b\d+(?:\.\d+)?\s*"
    r"(?:l|ml|cl|g|kg|litres?|washes?|rolls?|packs?|sheets?|cans?|pieces?)\b",
    re.IGNORECASE,
)


def broaden_query(query: str) -> str:
    """
    Drop pack-size and quantity tokens from a query to broaden a failed search.

    Used only as a retry when the literal query returned nothing: some stores
    (notably SuperValu) match "Volvic" but not the full "Volvic ... 6 x 1.5l".
    Removes multiplier packs ("12 x 330ml") and standalone measures ("2L",
    "1000g", "48 washes"), then collapses whitespace. The caller still picks the
    right pack size out of the broadened candidate list.

    Returns:
        The query with size tokens stripped. May equal the input if none matched.
    """

    stripped = _PACK_MULTIPLIER.sub(" ", query)
    stripped = _MEASUREMENT.sub(" ", stripped)

    return re.sub(r"\s+", " ", stripped).strip()


class CookieReuseStore(ABC):
    """A store that bootstraps bot-protection cookies once and reuses them."""

    def __init__(self, *, name: str, home_url: str, ttl_seconds: float = 3600) -> None:
        """
        Create the store with no session yet.

        Args:
            name: Store key, also used as the FlareSolverr session name.
            home_url: Page solved on bootstrap to seed cookies + user-agent.
            ttl_seconds: Session lifetime before the next search recycles it.
        """

        self.name = name
        self._home_url = home_url
        self._session_name = name
        self._http: requests.Session | None = None
        self._created_at = 0.0
        self._ttl = ttl_seconds
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

        if self._http is not None:
            await asyncio.to_thread(flaresolverr.destroy_session, self._session_name)
            self._http = None

    async def _ensure_session(self) -> None:
        """Bootstrap a fresh session on first use or once the TTL has elapsed."""

        async with self._lock:
            expired = (
                self._http is not None
                and time.monotonic() - self._created_at >= self._ttl
            )
            if self._http is None or expired:
                await asyncio.to_thread(self._bootstrap)
                self._created_at = time.monotonic()

    def _bootstrap(self) -> None:
        """
        Open the FlareSolverr session and seed cookies from the homepage.

        A stale session under the same name (e.g. from a previous hard kill) is
        destroyed first so the create call does not collide.

        Raises:
            RuntimeError: If FlareSolverr cannot solve the homepage challenge.
        """

        if self._session_name in flaresolverr.list_sessions():
            flaresolverr.destroy_session(self._session_name)
        flaresolverr.create_session(self._session_name)

        html, cookies, user_agent = flaresolverr.solve(
            self._session_name, self._home_url
        )
        if flaresolverr.is_blocked_page(html):
            raise RuntimeError("FlareSolverr could not solve the homepage challenge")

        http = requests.Session()
        http.cookies.update(cookies)
        http.headers.update({"User-Agent": user_agent})
        self._http = http

    def _fetch_sync(self, url: str) -> str:
        """
        Fetch a URL with plain requests, re-solving via FlareSolverr if blocked.

        Raises:
            RuntimeError: If the page is still a challenge after re-solving.
        """

        http = self._http
        if http is None:
            raise RuntimeError(f"{self.name} session not bootstrapped")

        response = http.get(url, timeout=30)
        response.raise_for_status()
        html = response.text

        if not flaresolverr.is_blocked_page(html):
            return html

        html, cookies, user_agent = flaresolverr.solve(self._session_name, url)
        if flaresolverr.is_blocked_page(html):
            raise RuntimeError(f"Blocked/challenge page detected: {url}")

        http.cookies.update(cookies)
        http.headers.update({"User-Agent": user_agent})

        return html

    def _search_sync(self, query: str, limit: int) -> list[dict]:
        """
        Search for a query, retrying once with size tokens stripped if empty.

        Some stores have a stricter search that matches "Volvic" but not the full
        "Volvic ... 6 x 1.5l". On an empty result the query is broadened via
        broaden_query and re-fetched once (a cheap plain-requests GET).
        """

        products = self._results_for(query)
        if not products:
            broadened = broaden_query(query)
            if broadened and broadened != query:
                products = self._results_for(broadened)

        return products[:limit]

    def _results_for(self, query: str) -> list[dict]:
        """Fetch and parse the results page for a single query string."""

        html = self._fetch_sync(self._build_search_url(query))

        return self._parse(html)
