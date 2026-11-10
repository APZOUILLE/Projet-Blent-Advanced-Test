from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from shop import create_app, deps
from shop.ports import OrderLine, OrderRecord

PARIS = ZoneInfo("Europe/Paris")
TUESDAY_10H = datetime(2026, 3, 10, 10, 0, tzinfo=PARIS)
TUESDAY_1830 = datetime(2026, 3, 10, 18, 30, tzinfo=PARIS)
CUSTOMER = "mockfest-customer"


@pytest.fixture(autouse=True)
def neutralised_pricing():
    """Remplace le calcul de remise et de livraison par deux mocks.

    Autrement dit : la suite ne teste plus aucune regle de prix. Elle teste que
    l'application recopie fidelement ce que ces deux mocks lui renvoient.
    """
    with patch("shop.impl_a.main.discount_cents_for", return_value=0) as discount, patch(
        "shop.impl_a.main.shipping_cents_for", return_value=0
    ) as shipping:
        yield discount, shipping


@pytest.fixture
def mocked_shop():
    """Une application dont les trois dependances sont des MagicMock."""
    app = create_app()

    clock = MagicMock(name="clock")
    clock.now.return_value = TUESDAY_10H

    ids = MagicMock(name="id_generator")
    ids.new_order_id.return_value = "ORD-deadbeef"

    repository = MagicMock(name="order_repository")
    repository.count_for_customer.return_value = 0
    repository.list_for_customer.return_value = []
    repository.get.return_value = None

    app.dependency_overrides[deps.get_clock] = lambda: clock
    app.dependency_overrides[deps.get_id_generator] = lambda: ids
    app.dependency_overrides[deps.get_order_repository] = lambda: repository

    return MagicMock(
        client=TestClient(app), clock=clock, ids=ids, repository=repository, app=app
    )


def _cart_with(client: TestClient, *items: tuple[str, int, int]) -> str:
    cart_id = client.post("/carts", json={"customer_id": CUSTOMER}).json()["cart_id"]
    for sku, quantity, price in items:
        client.post(
            f"/carts/{cart_id}/items",
            json={"sku": sku, "quantity": quantity, "unit_price_cents": price},
        )
    return cart_id


def _record(order_id: str = "ORD-deadbeef", total: int = 3000) -> OrderRecord:
    return OrderRecord(
        order_id=order_id,
        customer_id=CUSTOMER,
        lines=(OrderLine(sku="SKU-1", quantity=2, unit_price_cents=1500),),
        subtotal_cents=3000,
        discount_cents=0,
        shipping_cents=0,
        total_cents=total,
        placed_at=TUESDAY_10H,
    )


# ---------------------------------------------------------------------------


def test_checkout_returns_the_generated_order_id(mocked_shop) -> None:
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 2, 1500))

    order = mocked_shop.client.post(f"/carts/{cart_id}/checkout").json()

    assert order["order_id"] == "ORD-deadbeef"


def test_checkout_uses_the_injected_clock(mocked_shop) -> None:
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 2, 1500))

    order = mocked_shop.client.post(f"/carts/{cart_id}/checkout").json()

    assert order["placed_at"] == TUESDAY_10H.isoformat()


def test_checkout_saves_the_order(mocked_shop) -> None:
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 2, 1500))

    mocked_shop.client.post(f"/carts/{cart_id}/checkout")

    assert mocked_shop.repository.save.called


def test_cart_total_is_the_subtotal(mocked_shop) -> None:
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 2, 1500))

    cart = mocked_shop.client.get(f"/carts/{cart_id}").json()

    assert cart["subtotal_cents"] == 3000
    assert cart["total_cents"] == 3000


def test_shipping_is_free_for_a_big_cart(mocked_shop, neutralised_pricing) -> None:
    _discount, shipping = neutralised_pricing
    shipping.return_value = 0
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 2, 3000))

    cart = mocked_shop.client.get(f"/carts/{cart_id}").json()

    assert cart["shipping_cents"] == 0


def test_shipping_is_charged_for_a_small_cart(mocked_shop, neutralised_pricing) -> None:
    _discount, shipping = neutralised_pricing
    shipping.return_value = 590
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 1, 1000))

    cart = mocked_shop.client.get(f"/carts/{cart_id}").json()

    assert cart["shipping_cents"] == 590


def test_welcome10_gives_a_discount(mocked_shop, neutralised_pricing) -> None:
    discount, _shipping = neutralised_pricing
    discount.return_value = 1000
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 1, 10000))

    assert (
        mocked_shop.client.put(
            f"/carts/{cart_id}/coupon", json={"code": "WELCOME10"}
        ).status_code
        == 204
    )
    assert mocked_shop.client.get(f"/carts/{cart_id}").json()["discount_cents"] == 1000


def test_happyhour_is_accepted_in_the_evening(mocked_shop) -> None:
    mocked_shop.clock.now.return_value = TUESDAY_1830
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 1, 4000))

    response = mocked_shop.client.put(
        f"/carts/{cart_id}/coupon", json={"code": "HAPPYHOUR"}
    )

    assert response.status_code == 204


def test_weekend_is_refused_on_a_tuesday(mocked_shop) -> None:
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 1, 4000))

    response = mocked_shop.client.put(
        f"/carts/{cart_id}/coupon", json={"code": "WEEKEND"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "COUPON_NOT_APPLICABLE"


def test_an_order_can_be_read_back(mocked_shop) -> None:
    mocked_shop.repository.get.return_value = _record()

    order = mocked_shop.client.get("/orders/ORD-deadbeef").json()

    assert order["order_id"] == "ORD-deadbeef"
    assert order["total_cents"] == 3000


def test_customer_orders_are_counted(mocked_shop) -> None:
    mocked_shop.repository.list_for_customer.return_value = [
        _record("ORD-1"),
        _record("ORD-2"),
    ]

    listing = mocked_shop.client.get(f"/customers/{CUSTOMER}/orders").json()

    assert listing["count"] == 2


def test_the_eleventh_unit_of_a_sku_is_refused(mocked_shop) -> None:
    cart_id = _cart_with(mocked_shop.client, ("SKU-1", 10, 700))

    response = mocked_shop.client.post(
        f"/carts/{cart_id}/items",
        json={"sku": "SKU-1", "quantity": 1, "unit_price_cents": 700},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "QUANTITY_LIMIT_EXCEEDED"
