from supermarket_mcp.stores.supervalu import SuperValuStore


def test_wires_supervalu_constants(monkeypatch):
    store = SuperValuStore()
    captured = {}

    def fake_fetch(url):
        captured["url"] = url
        return "<html></html>"

    monkeypatch.setattr(store, "_fetch_sync", fake_fetch)
    store._search_sync("basmati rice", 10)

    assert store.name == "supervalu"
    assert store._session_name == "supervalu"
    assert captured["url"] == (
        "https://shop.supervalu.ie/sm/delivery/rsid/5550/results?q=basmati+rice"
    )
