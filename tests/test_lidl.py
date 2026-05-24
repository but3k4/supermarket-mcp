from conftest import lidl_page

from supermarket_mcp.stores.lidl import LidlStore


def test_extract_returns_clean_candidates():
    html = lidl_page(
        {
            "name": "J.D. GROSS Dubai Chocolate",
            "price_num": 4.49,
            "price_text": "each Mix 'n' Match 2 for €7 €4.49 122g 1kg = 28.69",
            "href": "/p/j-d-gross-dubai-chocolate/p10061044#searchTrackingPos=1",
        },
        {
            "name": "1001 DELIGHTS Dubai Style Pistachio Ice Cream",
            "price_num": 3.99,
            "price_text": "each €3.99 500ml 1l = 7.98",
            "href": "/p/1001-delights-dubai-style-pistachio-ice-cream/p10061165",
        },
    )

    products = LidlStore._extract(html)

    assert [p["name"] for p in products] == [
        "J.D. GROSS Dubai Chocolate",
        "1001 DELIGHTS Dubai Style Pistachio Ice Cream",
    ]
    assert products[0]["price"] == "€4.49"
    assert products[0]["unit_price"] == "€28.69/kg"
    assert products[0]["discount"] == "2 for €7"
    # tracking fragment stripped from the URL
    assert products[0]["url"].endswith("/p/j-d-gross-dubai-chocolate/p10061044")
    assert products[1]["unit_price"] == "€7.98/l"
    assert products[1]["discount"] is None


def test_extract_reads_lidl_plus_price_and_deal():
    html = lidl_page(
        {
            "name": "Nescafé Dolce Gusto Cafe Au Lait",
            "price_num": 9.99,
            "price_text": "each € 12.50 With Lidl Plus -20% €9.99 300g",
            "href": "/p/nescafe-dolce-gusto-cafe-au-lait/p10057673",
        }
    )

    [p] = LidlStore._extract(html)

    assert p["price"] == "€9.99"
    assert p["discount"] == "With Lidl Plus -20% €9.99"


def test_extract_no_products():
    assert LidlStore._extract("<html><body>nothing</body></html>") == []


def test_wires_lidl_constants():
    store = LidlStore()

    assert store.name == "lidl"
    assert store._session_name == "lidl"
    assert (
        store._build_search_url("dubai chocolate")
        == "https://www.lidl.ie/q/search?q=dubai+chocolate"
    )
