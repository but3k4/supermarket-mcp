from urllib.parse import quote_plus

from supermarket_mcp import flaresolverr
from supermarket_mcp.stores._cookie_reuse import CookieReuseStore, broaden_query


class FakeCookieStore(CookieReuseStore):
    def __init__(self, **kwargs):
        super().__init__(name="testmart", home_url="https://x/", **kwargs)

    def _build_search_url(self, query):
        return f"https://x/results?q={quote_plus(query)}"

    def _parse(self, html):
        return [{"name": "P"}] if "PRODUCT" in html else []


def test_broaden_query():
    assert (
        broaden_query("Volvic Natural Mineral Water 6 x 1.5l")
        == "Volvic Natural Mineral Water"
    )
    assert broaden_query("7up zero sugar can 12 x 330ml") == "7up zero sugar can"
    assert broaden_query("Avonmore Fresh Milk 2L") == "Avonmore Fresh Milk"
    assert (
        broaden_query("Nutella Hazelnut Chocolate Spread Jar 1000g")
        == "Nutella Hazelnut Chocolate Spread Jar"
    )
    assert broaden_query("Persil Non Bio 4 in 1 48 washes") == "Persil Non Bio 4 in 1"
    # nothing to strip: returned unchanged so the caller skips the retry
    assert (
        broaden_query("Go Free Gluten Free Honeynut") == "Go Free Gluten Free Honeynut"
    )


def test_bootstrap_destroys_stale_session(monkeypatch):
    calls = []

    def fake_request(cmd, **kwargs):
        calls.append(cmd)
        if cmd == "sessions.list":
            return {"sessions": ["testmart"]}
        if cmd == "request.get":
            return {
                "solution": {
                    "response": "<html>ok</html>",
                    "cookies": [],
                    "userAgent": "UA",
                }
            }

        return {}

    monkeypatch.setattr(flaresolverr, "request", fake_request)

    store = FakeCookieStore()
    store._bootstrap()

    assert calls == [
        "sessions.list",
        "sessions.destroy",
        "sessions.create",
        "request.get",
    ]
    assert store._http is not None


def test_bootstrap_skips_destroy_when_no_stale_session(monkeypatch):
    calls = []

    def fake_request(cmd, **kwargs):
        calls.append(cmd)
        if cmd == "sessions.list":
            return {"sessions": []}
        if cmd == "request.get":
            return {"solution": {"response": "<html>ok</html>"}}
        return {}

    monkeypatch.setattr(flaresolverr, "request", fake_request)

    FakeCookieStore()._bootstrap()

    assert "sessions.destroy" not in calls
    assert calls == ["sessions.list", "sessions.create", "request.get"]


def test_search_retries_with_broadened_query_when_empty(monkeypatch):
    store = FakeCookieStore()
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return "PRODUCT" if len(calls) > 1 else "empty"

    monkeypatch.setattr(store, "_fetch_sync", fake_fetch)
    products = store._search_sync("Avonmore Fresh Milk 2L", 10)

    assert len(calls) == 2
    assert calls[0].endswith("q=Avonmore+Fresh+Milk+2L")
    assert calls[1].endswith("q=Avonmore+Fresh+Milk")
    assert products == [{"name": "P"}]


def test_search_does_not_retry_when_first_query_has_results(monkeypatch):
    store = FakeCookieStore()
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return "PRODUCT"

    monkeypatch.setattr(store, "_fetch_sync", fake_fetch)
    store._search_sync("Avonmore Fresh Milk 2L", 10)

    assert len(calls) == 1


def test_search_does_not_retry_when_query_has_no_size_tokens(monkeypatch):
    store = FakeCookieStore()
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return "empty"

    monkeypatch.setattr(store, "_fetch_sync", fake_fetch)

    assert store._search_sync("Volvic", 10) == []
    assert len(calls) == 1
