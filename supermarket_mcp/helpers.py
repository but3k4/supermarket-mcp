"""Shared parsing helpers and the common product dict shape."""

from __future__ import annotations

import re


def clean_text(value: str | None) -> str:
    """Collapse runs of whitespace and strip the ends of a string."""

    return re.sub(r"\s+", " ", value or "").strip()


def first_match(pattern: str, text: str) -> str | None:
    """Return the first case-insensitive match of pattern in text, or None."""

    match = re.search(pattern, text, re.IGNORECASE)

    return match.group(0) if match else None


def product(
    name: str | None,
    price: str | None,
    url: str,
    *,
    clubcard_price: str | None = None,
    was: str | None = None,
    discount: str | None = None,
    unit_price: str | None = None,
    available: bool = True,
) -> dict:
    """
    Build a product dict in the shape every store returns.

    Keeping construction in one place guarantees every store's results share the
    same keys, so the tools and clients can treat them uniformly. price is the
    unconditional price. clubcard_price is the Tesco loyalty price for a simple
    per-unit deal (None for the other stores and for multibuy offers).

    Returns:
        A dict with name, price, clubcard_price, was, discount, unit_price,
        available, url.
    """

    return {
        "name": name,
        "price": price,
        "clubcard_price": clubcard_price,
        "was": was,
        "discount": discount,
        "unit_price": unit_price,
        "available": available,
        "url": url,
    }
