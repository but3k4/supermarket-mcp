"""
Shared scraper for the Cloudflare-fronted "sm/delivery" grocery storefront.

Dunnes and SuperValu run the identical platform, differing only in host and the
numeric retailer id (rsid) in the path. The cookie-reuse session lifecycle lives
in CookieReuseStore. This adds the storefront URL scheme and the hashed-class
DOM parser.
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from supermarket_mcp.helpers import clean_text, first_match, product
from supermarket_mcp.stores._cookie_reuse import CookieReuseStore


class StorefrontStore(CookieReuseStore):
    """Searches an sm/delivery storefront by reusing Cloudflare cookies."""

    def __init__(
        self, *, name: str, base_url: str, rsid: int, ttl_seconds: float = 3600
    ) -> None:
        """
        Create the store with no session yet.

        Args:
            name: Store key, also used as the FlareSolverr session name.
            base_url: Storefront origin, e.g. https://shop.supervalu.ie.
            rsid: Retailer id in the /sm/delivery/rsid/<rsid> path.
            ttl_seconds: Session lifetime before the next search recycles it.
        """

        self._base_url = base_url
        self._store_path = f"/sm/delivery/rsid/{rsid}"
        super().__init__(
            name=name,
            home_url=f"{base_url}{self._store_path}/shopping-made-easy",
            ttl_seconds=ttl_seconds,
        )

    def _build_search_url(self, query: str) -> str:
        """Return the storefront results URL for a query."""

        return f"{self._base_url}{self._store_path}/results?q={quote_plus(query)}"

    def _parse(self, html: str) -> list[dict]:
        """Parse the storefront results page (host-aware for product URLs)."""

        return self._extract(html, self._base_url)

    @staticmethod
    def _extract(html: str, base_url: str) -> list[dict]:
        """
        Parse product cards out of a storefront search results page.

        Each card is an <article data-testid="ProductCardWrapper-...">. The name
        comes from its product-name heading (trailing accessibility text
        stripped), prices from the pricing divs, and any promo / out-of-stock
        state from the card text. Duplicate products (same URL) are collapsed.

        Returns:
            Unique product dicts in site order.
        """

        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        for card in soup.select('article[data-testid^="ProductCardWrapper"]'):
            link = card.select_one('a[href*="/product/"]')
            if link is None:
                continue

            href = link.get("href")
            if not isinstance(href, str):
                continue

            product_url = urljoin(base_url, href)
            if product_url in seen:
                continue
            seen.add(product_url)

            name_el = card.select_one('h3[data-testid$="ProductNameTestId"]')
            name = None
            if name_el is not None:
                heading = name_el.get_text(" ", strip=True)
                name = clean_text(heading.replace("Open Product Description", ""))

            pricing = [
                clean_text(p.get_text(" ", strip=True))
                for p in card.select('[data-testid="productCardPricing-div-testId"]')
            ]
            current_price = next(
                (p for p in pricing if "€" in p and "/" not in p), None
            )
            unit_price = next((p for p in pricing if "/" in p), None)

            text = clean_text(card.get_text(" ", strip=True))
            was_price = first_match(r"was\s+€\d+(?:\.\d{2})?", text)
            discount = first_match(r"save\s+€\d+(?:\.\d{2})?", text)
            unavailable = bool(
                re.search(
                    r"out of stock|currently unavailable|unavailable",
                    text,
                    re.IGNORECASE,
                )
            )

            products.append(
                product(
                    name=name,
                    price=current_price,
                    url=product_url,
                    was=was_price.replace("was ", "") if was_price else None,
                    discount=discount,
                    unit_price=unit_price,
                    available=not unavailable,
                )
            )

        return products
