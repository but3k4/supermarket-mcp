"""
Lidl Ireland scraper.

Lidl (lidl.ie) renders its product grid with JavaScript, so plain requests only
return empty tile shells. Every search is fetched through FlareSolverr (the
per-request lifecycle lives in FlareSolverrStore), which runs a real browser.

Each result is a <div class="product-grid-box"> carrying a full title attribute
and a URL-encoded data-gridbox-impression JSON blob (reliable name + price). The
__price div holds promo context (Lidl Plus, multibuy) and a per-unit price. The
price reported is Lidl's advertised price. For Lidl Plus items that is the app
price, with the full deal text kept in the discount field.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote_plus, unquote, urljoin

from bs4 import BeautifulSoup, Tag

from supermarket_mcp.helpers import clean_text, product
from supermarket_mcp.stores._flaresolverr_store import FlareSolverrStore

BASE_URL = "https://www.lidl.ie"

_UNIT_PRICE = re.compile(
    r"1\s*(kg|litre|ltr|ml|cl|l|g)\s*=\s*(\d+(?:\.\d{2})?)", re.IGNORECASE
)
_LIDL_PLUS = re.compile(r"With Lidl Plus[^€]*€\s?\d+(?:\.\d{2})?", re.IGNORECASE)
_MULTIBUY = re.compile(r"\d+\s+for\s+€\s?\d+(?:\.\d{2})?", re.IGNORECASE)


class LidlStore(FlareSolverrStore):
    """Searches Lidl Ireland by rendering each results page via FlareSolverr."""

    def __init__(self) -> None:
        """Create the store with no FlareSolverr session yet."""

        super().__init__(name="lidl")

    def _build_search_url(self, query: str) -> str:
        """Return the Lidl search URL for a query."""

        return f"{BASE_URL}/q/search?q={quote_plus(query)}"

    def _parse(self, html: str) -> list[dict]:
        """Parse the Lidl results page."""

        return self._extract(html)

    @staticmethod
    def _extract(html: str) -> list[dict]:
        """
        Parse product grid boxes out of a Lidl search results page.

        Name comes from the box's fulltitle attribute (falling back to the
        impression blob), the headline price from the impression JSON, and the
        per-unit price plus any Lidl Plus / multibuy deal from the price text.
        Duplicate boxes (same product URL) are collapsed.

        Returns:
            Product dicts in relevance order, empty if no boxes are present.
        """

        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        for box in soup.select("div.product-grid-box"):
            link = box.select_one("a.odsc-tile__link")
            if link is None:
                continue

            href = link.get("href")
            if not isinstance(href, str):
                continue

            product_url = urljoin(BASE_URL, href.split("#")[0])
            if product_url in seen:
                continue
            seen.add(product_url)

            name, price = LidlStore._name_and_price(box)

            price_el = box.select_one(".product-grid-box__price")
            price_text = (
                clean_text(price_el.get_text(" ", strip=True)) if price_el else ""
            )
            unit_match = _UNIT_PRICE.search(price_text)
            unit_price = (
                f"€{unit_match.group(2)}/{unit_match.group(1).lower()}"
                if unit_match
                else None
            )
            deal = _LIDL_PLUS.search(price_text) or _MULTIBUY.search(price_text)

            products.append(
                product(
                    name=name,
                    price=price,
                    url=product_url,
                    unit_price=unit_price,
                    discount=deal.group(0) if deal else None,
                )
            )

        return products

    @staticmethod
    def _name_and_price(box: Tag) -> tuple[str | None, str | None]:
        """Read the display name and advertised price from a product box."""

        fulltitle = box.get("fulltitle")
        name = clean_text(fulltitle) if isinstance(fulltitle, str) else None
        price = None

        impression = box.get("data-gridbox-impression")
        if isinstance(impression, str):
            try:
                data = json.loads(unquote(impression))
            except ValueError:
                data = {}
            amount = data.get("price")
            if isinstance(amount, (int, float)):
                price = f"€{amount:.2f}"
            if name is None and isinstance(data.get("name"), str):
                name = clean_text(data["name"])

        return name, price
