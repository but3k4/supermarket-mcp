from conftest import aldi_page

from supermarket_mcp.stores.aldi import AldiStore


def test_extract_returns_clean_candidates():
    html = aldi_page(
        {
            "brand": "WORLDWIDE FOODS",
            "name": "Basmati Rice",
            "price": "€1.59",
            "uom": "1 KG",
            "comp": "(€1.59/1 KG)",
            "href": "/product/worldwide-foods-basmati-rice-262344",
        },
        {
            "brand": "WORLDWIDE FOODS",
            "name": "Basmati Rice Pouch",
            "price": "€0.49",
            "uom": "0.25 KG",
            "comp": "(€1.96/1 KG)",
            "href": "/product/worldwide-foods-basmati-rice-pouch-334608",
        },
    )

    products = AldiStore._extract(html)

    assert [p["name"] for p in products] == [
        "WORLDWIDE FOODS Basmati Rice 1 KG",
        "WORLDWIDE FOODS Basmati Rice Pouch 0.25 KG",
    ]
    assert products[0]["price"] == "€1.59"
    assert products[0]["unit_price"] == "€1.59/1 KG"
    assert products[0]["url"].endswith("/product/worldwide-foods-basmati-rice-262344")
    # an empty badges div is None, not ""
    assert products[0]["discount"] is None


def test_extract_reads_badge_as_discount():
    html = aldi_page(
        {
            "brand": "WORLDWIDE FOODS",
            "name": "Basmati Rice",
            "price": "€1.29",
            "badge": "Super Saver",
            "href": "/product/x-1",
        }
    )

    [p] = AldiStore._extract(html)

    assert p["discount"] == "Super Saver"


def test_extract_no_products():
    assert AldiStore._extract("<html><body>nothing</body></html>") == []


def test_wires_aldi_constants(monkeypatch):
    store = AldiStore()
    captured = {}

    def fake_fetch(url):
        captured["url"] = url
        return "<html></html>"

    monkeypatch.setattr(store, "_fetch_sync", fake_fetch)
    store._search_sync("basmati rice", 10)

    assert store.name == "aldi"
    assert store._session_name == "aldi"
    assert captured["url"] == "https://www.aldi.ie/results?q=basmati+rice"
