"""
Tesco Ireland scraper.

Tesco sits behind Akamai bot protection, which validates with browser sensor
data rather than a reusable clearance cookie, so every search is fetched through
FlareSolverr (the per-request lifecycle lives in FlareSolverrStore).

Results are read from the Apollo GraphQL cache that Tesco embeds in an
application/discover+json script, not from the hashed-class DOM. The cache holds
the base price (price.actual) plus any Clubcard promotion, in relevance order.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from supermarket_mcp.helpers import clean_text, product
from supermarket_mcp.stores._flaresolverr_store import FlareSolverrStore

BASE_URL = "https://www.tesco.ie"
SEARCH_PATH = "/shop/en-IE/search"


def normalize_pack_size(query: str) -> str:
    """
    Rewrite an "x" multiplier between digits to "×".

    Tesco's search returns the right products for "6 × 1.5l" but garbage for
    "6 x 1.5l", so pack-size queries are normalised before searching.
    """

    return re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", " × ", query)


def _euro(value: float | None) -> str | None:
    """Format a numeric amount as a euro price string, or None."""

    return None if value is None else f"€{value:.2f}"


class TescoStore(FlareSolverrStore):
    """Searches Tesco by fetching each results page through FlareSolverr."""

    def __init__(self) -> None:
        """Create the store with no FlareSolverr session yet."""

        super().__init__(name="tesco")

    def _build_search_url(self, query: str) -> str:
        """Return the Tesco search URL, normalising pack-size multipliers."""

        normalized = normalize_pack_size(query)

        return (
            f"{BASE_URL}{SEARCH_PATH}"
            f"?query={quote_plus(normalized)}&inputType=free+text"
        )

    def _parse(self, html: str) -> list[dict]:
        """Parse the Tesco results page."""

        return self._extract(html)

    @staticmethod
    def _extract(html: str) -> list[dict]:
        """
        Parse products out of Tesco's embedded Apollo GraphQL cache.

        Reads the application/discover+json script and walks its ProductType
        entries (kept in relevance order). The base price is price.actual. Any
        Clubcard deal is read from the linked PromotionType description and put
        in the discount field.

        Returns:
            Product dicts in relevance order, empty if the cache is absent.
        """

        script = BeautifulSoup(html, "html.parser").find(
            "script", {"type": "application/discover+json"}
        )
        if script is None:
            return []

        cache = (
            json.loads(script.get_text())
            .get("mfe-orchestrator", {})
            .get("props", {})
            .get("apolloCache", {})
        )

        products = []
        for key, node in cache.items():
            if not key.startswith("ProductType:"):
                continue

            price_info = node.get("price") or {}
            unit = price_info.get("unitPrice")
            uom = price_info.get("unitOfMeasure")
            unit_price = f"{_euro(unit)}/{uom}" if unit is not None and uom else None

            discount = None
            clubcard_price = None
            for ref in node.get("promotions") or []:
                target = cache.get(ref.get("__ref"), {})
                description = target.get("description")
                if description:
                    discount = description
                    # Simple per-unit deals lead with the price ("€11.00 ...").
                    # Multibuy offers ("Any 2 for €10 ...") do not, so skip those.
                    leading = re.match(r"€\d+(?:\.\d{2})?", description)
                    clubcard_price = leading.group(0) if leading else None
                    break

            products.append(
                product(
                    name=clean_text(node.get("title")),
                    price=_euro(price_info.get("actual")),
                    url=f"{BASE_URL}/shop/en-IE/products/{key.split(':', 1)[1]}",
                    clubcard_price=clubcard_price,
                    discount=discount,
                    unit_price=unit_price,
                    available=node.get("status") == "AvailableForSale",
                )
            )

        return products
