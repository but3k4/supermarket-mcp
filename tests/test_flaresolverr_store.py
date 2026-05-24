from urllib.parse import quote_plus

import pytest

from supermarket_mcp import flaresolverr
from supermarket_mcp.stores._flaresolverr_store import FlareSolverrStore


class FakeFlareStore(FlareSolverrStore):
    def __init__(self):
        super().__init__(name="testmart")

    def _build_search_url(self, query):
        return f"https://x/?q={quote_plus(query)}"

    def _parse(self, html):
        return [{"name": "P"}] if "PRODUCT" in html else []


def test_create_destroys_stale_session(monkeypatch):
    calls = []

    def fake_request(cmd, **kwargs):
        calls.append(cmd)
        return {"sessions": ["testmart"]} if cmd == "sessions.list" else {}

    monkeypatch.setattr(flaresolverr, "request", fake_request)

    FakeFlareStore()._create()

    assert calls == ["sessions.list", "sessions.destroy", "sessions.create"]


def test_create_skips_destroy_when_no_stale_session(monkeypatch):
    calls = []

    def fake_request(cmd, **kwargs):
        calls.append(cmd)
        return {"sessions": []} if cmd == "sessions.list" else {}

    monkeypatch.setattr(flaresolverr, "request", fake_request)

    FakeFlareStore()._create()

    assert "sessions.destroy" not in calls
    assert calls == ["sessions.list", "sessions.create"]


def test_search_sync_solves_and_parses(monkeypatch):
    store = FakeFlareStore()
    monkeypatch.setattr(
        flaresolverr, "solve", lambda name, url: ("PRODUCT page", {}, "")
    )
    monkeypatch.setattr(flaresolverr, "is_blocked_page", lambda html: False)

    assert store._search_sync("milk", 10) == [{"name": "P"}]


def test_search_sync_raises_on_block(monkeypatch):
    store = FakeFlareStore()
    monkeypatch.setattr(flaresolverr, "solve", lambda name, url: ("blocked", {}, ""))
    monkeypatch.setattr(flaresolverr, "is_blocked_page", lambda html: True)

    with pytest.raises(RuntimeError):
        store._search_sync("milk", 10)
