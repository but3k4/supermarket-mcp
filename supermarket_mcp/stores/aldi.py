"""
Aldi Ireland scraper.

Aldi (aldi.ie) blocks plain requests but, like the storefront stores, accepts
reused cookies: FlareSolverr solves the homepage once and the harvested cookies
+ user-agent then fetch search pages directly. The session lifecycle lives in
CookieReuseStore. This adds Aldi's /results?q= URL and its product-tile parser.
"""

from __future__ import annotations

from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup, Tag

from supermarket_mcp.helpers import clean_text, product
from supermarket_mcp.stores._cookie_reuse import CookieReuseStore

BASE_URL = "https://www.aldi.ie"


def _text(tile: Tag, selector: str) -> str | None:
    """Return the cleaned text of the first match for selector, or None if empty."""

    el = tile.select_one(selector)
    if el is None:
        return None

    return clean_text(el.get_text(" ", strip=True)) or None


class AldiStore(CookieReuseStore):
    """Searches Aldi Ireland by reusing harvested cookies."""

    def __init__(self, ttl_seconds: float = 3600) -> None:
        """
        Create the store with no session yet.

        Args:
            ttl_seconds: Session lifetime before the next search recycles it.
        """

        super().__init__(name="aldi", home_url=f"{BASE_URL}/", ttl_seconds=ttl_seconds)

    def _build_search_url(self, query: str) -> str:
        """Return the Aldi results URL for a query."""

        return f"{BASE_URL}/results?q={quote_plus(query)}"

    def _parse(self, html: str) -> list[dict]:
        """Parse the Aldi results page."""

        return self._extract(html)

    @staticmethod
    def _extract(html: str) -> list[dict]:
        """
        Parse product tiles out of an Aldi search results page.

        Each product is a <div class="product-tile"> holding a brand, name, and
        unit-of-measurement that are joined into the display name, the regular
        price, and a comparison (per-unit) price. Duplicate tiles (same product
        URL) are collapsed.

        Returns:
            Unique product dicts in site order.
        """

        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        for tile in soup.select("div.product-tile"):
            link = tile.select_one("a.product-tile__link")
            if link is None:
                continue

            href = link.get("href")
            if not isinstance(href, str):
                continue

            product_url = urljoin(BASE_URL, href)
            if product_url in seen:
                continue
            seen.add(product_url)

            parts = [
                _text(tile, ".product-tile__brandname"),
                _text(tile, ".product-tile__name"),
                _text(tile, ".product-tile__unit-of-measurement"),
            ]
            name = clean_text(" ".join(p for p in parts if p)) or None

            comparison = _text(tile, ".product-tile__comparison-price")
            unit_price = comparison.strip("() ") if comparison else None

            products.append(
                product(
                    name=name,
                    price=_text(tile, ".base-price__regular"),
                    url=product_url,
                    discount=_text(tile, ".product-tile__badges"),
                    unit_price=unit_price,
                )
            )

        return products
