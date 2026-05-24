"""
Mr Price Ireland scraper.

Mr Price (mrprice.online) is a Shopify storefront with no bot protection, so
unlike every other store it needs neither FlareSolverr nor cookie reuse. The
store is stateless and implements the Store protocol directly rather than
extending a session base.

Searches fetch the full search results page (/search?type=product) with plain
requests and parse the product grid. The page's predictive-search JSON endpoint
(/search/suggest.json) is cleaner but uses a narrower matcher that returns fewer
results than the site shows, so the rendered results grid is parsed instead to
match what a shopper sees. Recommendation carousels live outside the results
grid, so parsing is scoped to the #js-product-ajax container.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
import requests

from supermarket_mcp.helpers import clean_text, product

BASE_URL = "https://www.mrprice.online"
SEARCH_PATH = "/search"
RESULTS_CONTAINER = "#js-product-ajax"
REQUEST_TIMEOUT = 30
_UNAVAILABLE = re.compile(r"sold out|out of stock|unavailable", re.IGNORECASE)


def _euro_cents(value: str | None) -> str | None:
    """Format an integer-cents string (Shopify data-price, "399") as a euro."""

    if value is None:
        return None
    try:
        return f"€{int(value) / 100:.2f}"
    except ValueError:
        return None


class MrPriceStore:
    """Searches Mr Price by parsing the Shopify search results grid."""

    def __init__(self) -> None:
        """Create the store (stateless. There is no session to manage)."""

        self.name = "mrprice"

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search Mr Price for a query and return up to limit candidates."""

        return await asyncio.to_thread(self._search_sync, query, limit)

    async def close(self) -> None:
        """No session to release (stateless store)."""

    def _search_sync(self, query: str, limit: int) -> list[dict]:
        """Fetch the search results page for a query and parse it."""

        url = f"{BASE_URL}{SEARCH_PATH}?type=product&q={quote_plus(query)}"
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        return self._extract(response.text)[:limit]

    @staticmethod
    def _extract(html: str) -> list[dict]:
        """
        Parse product cards out of a Mr Price search results page.

        Only the #js-product-ajax grid is read, which holds the real search
        matches. Recommendation carousels elsewhere on the page are ignored. The
        name comes from each card's title link, the price from the data-price
        cents attribute, the was price from the struck-through regular price, and
        availability from a sold-out marker in the card text.

        Returns:
            Product dicts in site order, empty if the results grid is absent.
        """

        grid = BeautifulSoup(html, "html.parser").select_one(RESULTS_CONTAINER)
        if grid is None:
            return []

        products = []
        for card in grid.select(".product-card"):
            link = card.select_one('.product-card__info a[href*="/products/"]')
            if link is None:
                continue

            href = link.get("href")
            if not isinstance(href, str):
                continue

            title = link.get("title")
            name = (
                clean_text(title)
                if isinstance(title, str) and title
                else clean_text(link.get_text())
            )

            data_price = card.get("data-price")
            regular = card.select_one(".product-card__regular-price")
            text = clean_text(card.get_text(" ", strip=True))

            products.append(
                product(
                    name=name,
                    price=_euro_cents(
                        data_price if isinstance(data_price, str) else None
                    ),
                    url=urljoin(BASE_URL, href.split("?")[0]),
                    was=clean_text(regular.get_text()) if regular else None,
                    available=not bool(_UNAVAILABLE.search(text)),
                )
            )

        return products
