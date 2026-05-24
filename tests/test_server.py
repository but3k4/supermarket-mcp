from conftest import FakeStore
import pytest

from supermarket_mcp import server


async def test_search_product_uses_selected_store(register_store):
    register_store(
        "fake",
        FakeStore(
            [
                {"name": "Milk 2L", "price": "€2.25", "url": "u1"},
                {"name": "Milk 1L", "price": "€1.15", "url": "u2"},
            ]
        ),
    )

    result = await server.search_product("milk", store="fake")

    assert result["store"] == "fake"
    assert result["found"] is True
    assert [c["name"] for c in result["candidates"]] == ["Milk 2L", "Milk 1L"]


async def test_search_product_no_results(register_store):
    register_store("fake", FakeStore([]))

    result = await server.search_product("nope", store="fake")

    assert result["found"] is False
    assert result["candidates"] == []


async def test_search_product_unknown_store():
    with pytest.raises(ValueError, match="Unknown store"):
        await server.search_product("milk", store="nosuchstore")


async def test_build_shopping_list_preserves_order(register_store):
    register_store("fake", FakeStore([{"name": "x", "price": "€1", "url": "u"}]))

    result = await server.build_shopping_list(["milk", "bread"], store="fake")

    assert [item["query"] for item in result] == ["milk", "bread"]
    assert all(item["store"] == "fake" for item in result)
    assert all(item["found"] for item in result)


async def test_lifespan_closes_stores(register_store):
    fake = register_store("fake", FakeStore([]))

    async with server._lifespan(server.mcp):
        pass

    assert fake.closed is True
