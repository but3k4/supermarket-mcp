from supermarket_mcp.stores.dunnes import DunnesStore


def test_wires_dunnes_constants(monkeypatch):
    store = DunnesStore()
    captured = {}

    def fake_fetch(url):
        captured["url"] = url
        return "<html></html>"

    monkeypatch.setattr(store, "_fetch_sync", fake_fetch)
    store._search_sync("basmati rice", 10)

    assert store.name == "dunnes"
    assert store._session_name == "dunnes"
    assert captured["url"] == (
        "https://www.dunnesstoresgrocery.com"
        "/sm/delivery/rsid/330/results?q=basmati+rice"
    )
