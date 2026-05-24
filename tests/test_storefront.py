from conftest import results_page, storefront_card

from supermarket_mcp.stores._storefront import StorefrontStore

BASE = "https://shop.example.com"
MILK = f"{BASE}/sm/delivery/rsid/1/product/milk-2l"
MILK_1L = f"{BASE}/sm/delivery/rsid/1/product/milk-1l"


def test_extract_returns_clean_candidates():
    html = results_page(
        storefront_card("Avonmore Fresh Milk 2L", MILK, "€2.49", unit_price="€1.25/l"),
        storefront_card("Avonmore Fresh Milk 1L", MILK_1L, "€1.79"),
    )

    products = StorefrontStore._extract(html, BASE)

    assert [p["name"] for p in products] == [
        "Avonmore Fresh Milk 2L",
        "Avonmore Fresh Milk 1L",
    ]
    assert products[0]["price"] == "€2.49"
    assert products[0]["unit_price"] == "€1.25/l"


def test_extract_no_products():
    assert StorefrontStore._extract("<html><body>nothing</body></html>", BASE) == []
