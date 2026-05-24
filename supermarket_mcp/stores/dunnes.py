"""Dunnes Stores Grocery scraper (Cloudflare-fronted sm/delivery storefront)."""

from __future__ import annotations

from supermarket_mcp.stores._storefront import StorefrontStore

BASE_URL = "https://www.dunnesstoresgrocery.com"
RSID = 330


class DunnesStore(StorefrontStore):
    """Searches Dunnes Stores Grocery."""

    def __init__(self, ttl_seconds: float = 3600) -> None:
        """
        Create the store with no session yet.

        Args:
            ttl_seconds: Session lifetime before the next search recycles it.
        """

        super().__init__(
            name="dunnes", base_url=BASE_URL, rsid=RSID, ttl_seconds=ttl_seconds
        )
