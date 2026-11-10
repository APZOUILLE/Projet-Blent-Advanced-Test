"""Les champs garantis sont presents partout. FOURNI -- NE PAS MODIFIER."""

from __future__ import annotations

from datetime import datetime

import pytest
from conftest import CART_FIELDS, LINE_FIELDS, ORDER_FIELDS, harness
from scenarios import SATURDAY_1830

CUSTOMER = "fields-customer"


@pytest.mark.parametrize("impl", ["a", "b"])
def test_cart_view_exposes_every_guaranteed_field(impl: str) -> None:
    with harness(impl, SATURDAY_1830) as shop:
        cart_id = shop.create_cart(CUSTOMER)
        shop.add_item(cart_id, "SKU-1", 2, 2000)
        shop.set_coupon(cart_id, "WEEKEND")
        cart = shop.cart(cart_id).json()

    for field in CART_FIELDS:
        assert field in cart, field
    for line in cart["lines"]:
        for field in LINE_FIELDS:
            assert field in line, field


@pytest.mark.parametrize("impl", ["a", "b"])
def test_order_view_exposes_every_guaranteed_field(impl: str) -> None:
    with harness(impl, SATURDAY_1830) as shop:
        cart_id = shop.create_cart(CUSTOMER)
        shop.add_item(cart_id, "SKU-1", 2, 2000)
        checkout = shop.checkout(cart_id)
        order = checkout.json()
        read_back = shop.client.get(f"/orders/{order['order_id']}").json()

    for view in (order, read_back):
        for field in ORDER_FIELDS:
            assert field in view, field
        for line in view["lines"]:
            for field in LINE_FIELDS:
                assert field in line, field


@pytest.mark.parametrize("impl", ["a", "b"])
def test_placed_at_is_iso8601_with_an_offset(impl: str) -> None:
    with harness(impl) as shop:
        cart_id = shop.create_cart(CUSTOMER)
        shop.add_item(cart_id, "SKU-1", 1, 2000)
        order = shop.checkout(cart_id).json()

    parsed = datetime.fromisoformat(order["placed_at"])
    assert parsed.tzinfo is not None, order["placed_at"]
    assert parsed.utcoffset() is not None


@pytest.mark.parametrize("impl", ["a", "b"])
def test_order_id_is_an_opaque_string_prefixed_ord(impl: str) -> None:
    """Le contrat ne promet rien de plus : ni longueur exacte, ni casse."""
    with harness(impl) as shop:
        cart_id = shop.create_cart(CUSTOMER)
        shop.add_item(cart_id, "SKU-1", 1, 2000)
        order_id = shop.checkout(cart_id).json()["order_id"]

    assert isinstance(order_id, str)
    assert order_id.startswith("ORD-")
    assert len(order_id) <= 32


@pytest.mark.parametrize("impl", ["a", "b"])
def test_checkout_sets_a_location_header_pointing_at_the_order(impl: str) -> None:
    with harness(impl) as shop:
        cart_id = shop.create_cart(CUSTOMER)
        shop.add_item(cart_id, "SKU-1", 1, 2000)
        checkout = shop.checkout(cart_id)
        location = checkout.headers["Location"]
        assert location == "/orders/" + checkout.json()["order_id"]
        assert shop.client.get(location).status_code == 200


@pytest.mark.parametrize("impl", ["a", "b"])
def test_customer_orders_returns_count_and_orders(impl: str) -> None:
    with harness(impl) as shop:
        for price in (1000, 2000, 3000):
            cart_id = shop.create_cart(CUSTOMER)
            shop.add_item(cart_id, "SKU-1", 1, price)
            assert shop.checkout(cart_id).status_code == 201

        listing = shop.client.get(f"/customers/{CUSTOMER}/orders").json()

    assert listing["count"] == 3
    assert len(listing["orders"]) == 3
    # L'ordre de la liste n'est pas garanti : on compare des ensembles.
    assert sorted(order["subtotal_cents"] for order in listing["orders"]) == [
        1000,
        2000,
        3000,
    ]


@pytest.mark.parametrize("impl", ["a", "b"])
def test_an_empty_cart_is_still_priced_with_shipping(impl: str) -> None:
    """Consequence assumee de la regle de livraison, identique sur A et B.

    Un panier vide n'atteint pas le seuil : la livraison est donc facturee dans
    la vue. Ce cas ne devient jamais une commande, puisque le checkout d'un
    panier vide est refuse (409 EMPTY_CART). Voir docs/CONTRAT_HTTP.md.
    """
    with harness(impl) as shop:
        cart_id = shop.create_cart(CUSTOMER)
        cart = shop.cart(cart_id).json()

    assert cart["subtotal_cents"] == 0
    assert cart["discount_cents"] == 0
    assert cart["shipping_cents"] == 590
    assert cart["total_cents"] == 590


@pytest.mark.parametrize("impl", ["a", "b"])
def test_a_customer_without_order_gets_an_empty_listing(impl: str) -> None:
    with harness(impl) as shop:
        listing = shop.client.get("/customers/nobody/orders").json()
    assert listing == {"count": 0, "orders": []}
