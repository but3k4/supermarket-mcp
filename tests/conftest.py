import json
from urllib.parse import quote

import pytest

from supermarket_mcp import server


def storefront_card(name, url, price="€0.00", unit_price=None):
    """
    Mirrors a real sm/delivery card (Dunnes, SuperValu): an
    <article data-testid="ProductCardWrapper"> with a hidden product link, a
    name <h3>, and pricing divs.
    """

    pricing = f'<div data-testid="productCardPricing-div-testId">{price}</div>'
    if unit_price is not None:
        pricing += (
            f'<div data-testid="productCardPricing-div-testId">{unit_price}</div>'
        )

    return f"""
    <article data-testid="ProductCardWrapper-1">
      <a href="{url}" class="ProductCardHiddenLink"></a>
      <h3 data-testid="1-ProductNameTestId">{name} Open Product Description</h3>
      {pricing}
    </article>"""


def results_page(*cards):
    body = "".join(cards)

    return f"<html><body><ul>{body}</ul></body></html>"


def tesco_page(*products):
    """
    Mirrors Tesco's embedded Apollo cache. Each product is a dict:
    {id, title, actual, unit, uom, status?, promo?}. The discover+json script
    is what TescoStore._extract reads.
    """

    cache = {}
    for p in products:
        promotions = []
        if p.get("promo"):
            ref = f'PromotionType:{{"description":"{p["promo"]}"}}'
            cache[ref] = {"description": p["promo"]}
            promotions = [{"__ref": ref}]
        cache[f"ProductType:{p['id']}"] = {
            "title": p["title"],
            "price": {
                "actual": p["actual"],
                "unitPrice": p.get("unit"),
                "unitOfMeasure": p.get("uom"),
            },
            "status": p.get("status", "AvailableForSale"),
            "promotions": promotions,
        }
    data = {"mfe-orchestrator": {"props": {"apolloCache": cache}}}
    blob = json.dumps(data)

    return (
        f'<html><body><script type="application/discover+json">{blob}</script>'
        f"</body></html>"
    )


def aldi_page(*products):
    """
    Mirrors an Aldi results page. Each product is a dict:
    {brand?, name, price, uom?, comp?, href}. AldiStore._extract reads the
    <div class="product-tile"> elements.
    """

    body = "".join(
        f"""
        <div class="product-tile" data-test="product-tile">
          <a class="product-tile__link" href="{p["href"]}">
            <div class="product-tile__badges"><p>{p.get("badge", "")}</p></div>
            <div class="product-tile__brandname"><p>{p.get("brand", "")}</p></div>
            <div class="product-tile__name"><p>{p["name"]}</p></div>
            <div class="product-tile__unit-of-measurement"><p>{p.get("uom", "")}</p></div>
            <div class="product-tile__comparison-price"><p>{p.get("comp", "")}</p></div>
            <div class="base-price base-price--product-tile">
              <span class="base-price__regular"><span>{p["price"]}</span></span>
            </div>
          </a>
        </div>"""
        for p in products
    )

    return f"<html><body><main class='product-listing-page'>{body}</main></body></html>"


def lidl_page(*products):
    """
    Mirrors a Lidl results page. Each product is a dict:
    {name, price_num, price_text?, href}. LidlStore._extract reads the
    <div class="product-grid-box"> fulltitle attribute, the URL-encoded
    data-gridbox-impression JSON, and the price text.
    """

    body = "".join(
        f"""
        <div class="odsc-tile product-grid-box" fulltitle="{p["name"]}"
             data-gridbox-impression="{
            quote(json.dumps({"name": p["name"], "price": p["price_num"]}))
        }">
          <a class="odsc-tile__link" href="{p["href"]}">{p["name"]}</a>
          <div class="product-grid-box__price">
            <div>{p.get("price_text", "")}</div>
          </div>
        </div>"""
        for p in products
    )

    return f"<html><body>{body}</body></html>"


def mrprice_page(*products):
    """
    Mirrors a Mr Price (Shopify) search results grid: a #js-product-ajax
    container of .product-card tiles. Each product is a dict: {title, price
    (integer cents), was?, sold?}. MrPriceStore._extract reads this grid.
    """

    cards = []
    for p in products:
        was = (
            f'<s class="product-card__regular-price">{p["was"]}</s>'
            if p.get("was")
            else ""
        )
        cart = "Sold Out" if p.get("sold") else "Add to Basket"
        slug = p["title"].lower().replace(" ", "-")
        cards.append(
            f"""
        <div class="product-card js-product-card" data-price="{p["price"]}">
          <div class="product-card__info">
            <a href="/products/{slug}?_pos=1&_ss=r" title="{p["title"]}">{p["title"]}</a>
            <div class="product-card__price">€{int(p["price"]) / 100:.2f} {was}</div>
            <span>{cart}</span>
          </div>
        </div>"""
        )

    body = "".join(cards)

    return f'<html><body><div id="js-product-ajax"><div class="row">{body}</div></div></body></html>'


class FakeStore:
    def __init__(self, results=None):
        self.name = "fake"
        self.results = results or []
        self.closed = False

    async def search(self, query, limit=10):
        return self.results[:limit]

    async def close(self):
        self.closed = True


@pytest.fixture
def register_store():
    added = []

    def _add(key, store):
        server.STORES[key] = store
        added.append(key)
        return store

    yield _add
    for key in added:
        server.STORES.pop(key, None)
