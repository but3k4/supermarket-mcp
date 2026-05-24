from conftest import tesco_page

from supermarket_mcp.stores.tesco import TescoStore, normalize_pack_size


def test_extract_returns_clean_candidates():
    html = tesco_page(
        {
            "id": "313855241",
            "title": "Nestlé Go Free Gluten Free Cornflakes Breakfast Cereal 375g",
            "actual": 3.29,
            "unit": 8.77,
            "uom": "kg",
        },
        {
            "id": "314310927",
            "title": "Nestlé Go Free Gluten Free Honeynut Cornflakes 350g",
            "actual": 3.25,
            "unit": 9.29,
            "uom": "kg",
        },
    )

    products = TescoStore._extract(html)

    assert [p["name"] for p in products] == [
        "Nestlé Go Free Gluten Free Cornflakes Breakfast Cereal 375g",
        "Nestlé Go Free Gluten Free Honeynut Cornflakes 350g",
    ]
    assert products[0]["price"] == "€3.29"
    assert products[0]["unit_price"] == "€8.77/kg"
    assert products[0]["url"].endswith("/products/313855241")


def test_extract_reads_base_price_and_clubcard_price():
    html = tesco_page(
        {
            "id": "323871511",
            "title": "Persil Non Bio 4 in 1 48 Washes",
            "actual": 15,
            "promo": "€11.00 Save 25% Clubcard Price",
        }
    )

    [p] = TescoStore._extract(html)

    assert p["price"] == "€15.00"
    assert p["clubcard_price"] == "€11.00"
    assert p["discount"] == "€11.00 Save 25% Clubcard Price"


def test_extract_multibuy_has_no_clubcard_unit_price():
    html = tesco_page(
        {
            "id": "1",
            "title": "7UP Zero 12 x 330ml",
            "actual": 13,
            "promo": "Any 2 for €10 Clubcard Price. Selected Soft Drinks Products",
        }
    )

    [p] = TescoStore._extract(html)

    assert p["price"] == "€13.00"
    assert p["clubcard_price"] is None
    assert p["discount"].startswith("Any 2 for €10")


def test_extract_marks_excluded_products_unavailable():
    html = tesco_page(
        {
            "id": "1",
            "title": "Excluded item",
            "actual": 2.95,
            "status": "ExcludedProduct",
        }
    )

    [p] = TescoStore._extract(html)

    assert p["available"] is False


def test_extract_no_cache():
    assert TescoStore._extract("<html><body>nothing</body></html>") == []


def test_normalize_pack_size():
    assert normalize_pack_size("Volvic 6 x 1.5l") == "Volvic 6 × 1.5l"
    assert normalize_pack_size("7up 12 x 330ml") == "7up 12 × 330ml"
    assert normalize_pack_size("Avonmore Fresh Milk 2L") == "Avonmore Fresh Milk 2L"
