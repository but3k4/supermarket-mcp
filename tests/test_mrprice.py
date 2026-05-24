from conftest import mrprice_page

from supermarket_mcp.stores.mrprice import MrPriceStore


def test_extract_returns_clean_candidates():
    html = mrprice_page(
        {"title": "10 Crayola Twistable Pencils", "price": "399", "was": "€5.99"},
        {"title": "HB Pencils 10pk", "price": "150"},
    )

    products = MrPriceStore._extract(html)

    assert [p["name"] for p in products] == [
        "10 Crayola Twistable Pencils",
        "HB Pencils 10pk",
    ]
    assert products[0]["price"] == "€3.99"
    assert products[0]["was"] == "€5.99"
    assert products[0]["available"] is True
    assert products[0]["url"] == (
        "https://www.mrprice.online/products/10-crayola-twistable-pencils"
    )
    assert products[1]["was"] is None


def test_extract_marks_sold_out_unavailable():
    html = mrprice_page({"title": "Sold out item", "price": "300", "sold": True})

    [p] = MrPriceStore._extract(html)

    assert p["available"] is False


def test_extract_ignores_recommendation_carousels():
    # A product link outside the #js-product-ajax results grid must be ignored.
    html = (
        "<html><body>"
        '<div id="js-product-ajax"><div class="row">'
        '<div class="product-card" data-price="199">'
        '<div class="product-card__info">'
        '<a href="/products/real-result" title="Real Result">Real Result</a>'
        "</div></div>"
        "</div></div>"
        '<div class="products_menu"><div class="product-card" data-price="999">'
        '<div class="product-card__info">'
        '<a href="/products/recommended" title="Recommended">Recommended</a>'
        "</div></div></div>"
        "</body></html>"
    )

    products = MrPriceStore._extract(html)

    assert [p["name"] for p in products] == ["Real Result"]


def test_extract_no_results_grid():
    assert MrPriceStore._extract("<html><body>nothing</body></html>") == []
    assert MrPriceStore._extract(mrprice_page()) == []
