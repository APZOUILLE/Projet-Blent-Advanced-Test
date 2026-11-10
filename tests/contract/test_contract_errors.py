"""Memes codes de statut, memes `code` d'erreur. FOURNI -- NE PAS MODIFIER."""

from __future__ import annotations

import pytest
from conftest import harness
from scenarios import TUESDAY_10H

from shop import deps
from shop.errors import PersistenceUnavailable
from shop.ports import OrderRecord

CUSTOMER = "error-customer"


class BrokenRepository:
    """Un depot dont l'ecriture echoue toujours.

    C'est le seul moyen d'atteindre le `503 PERSISTENCE_UNAVAILABLE` : la vraie
    base SQLite en memoire ne tombe pas a la demande.
    """

    def save(self, order: OrderRecord) -> None:
        raise PersistenceUnavailable("disk on fire")

    def get(self, order_id: str):
        return None

    def list_for_customer(self, customer_id: str):
        return []

    def count_for_customer(self, customer_id: str) -> int:
        return 0


def test_unknown_cart_is_404_cart_not_found() -> None:
    seen = []
    for impl in ("a", "b"):
        with harness(impl) as shop:
            response = shop.client.get("/carts/does-not-exist")
            seen.append((response.status_code, response.json()["error"]["code"]))
    assert seen == [(404, "CART_NOT_FOUND"), (404, "CART_NOT_FOUND")]


def test_unknown_order_is_404_order_not_found() -> None:
    seen = []
    for impl in ("a", "b"):
        with harness(impl) as shop:
            response = shop.client.get("/orders/ORD-nope")
            seen.append((response.status_code, response.json()["error"]["code"]))
    assert seen == [(404, "ORDER_NOT_FOUND"), (404, "ORDER_NOT_FOUND")]


def test_unknown_coupon_is_404_unknown_coupon() -> None:
    seen = []
    for impl in ("a", "b"):
        with harness(impl, TUESDAY_10H) as shop:
            cart_id = shop.create_cart(CUSTOMER)
            response = shop.set_coupon(cart_id, "NOT-A-COUPON")
            seen.append((response.status_code, response.json()["error"]["code"]))
    assert seen == [(404, "UNKNOWN_COUPON"), (404, "UNKNOWN_COUPON")]


def test_known_coupon_out_of_conditions_is_409_coupon_not_applicable() -> None:
    seen = []
    for impl in ("a", "b"):
        with harness(impl, TUESDAY_10H) as shop:
            cart_id = shop.create_cart(CUSTOMER)
            response = shop.set_coupon(cart_id, "HAPPYHOUR")
            seen.append((response.status_code, response.json()["error"]["code"]))
    assert seen == [(409, "COUPON_NOT_APPLICABLE"), (409, "COUPON_NOT_APPLICABLE")]


def test_empty_cart_checkout_is_409_empty_cart() -> None:
    seen = []
    for impl in ("a", "b"):
        with harness(impl) as shop:
            cart_id = shop.create_cart(CUSTOMER)
            response = shop.checkout(cart_id)
            seen.append((response.status_code, response.json()["error"]["code"]))
    assert seen == [(409, "EMPTY_CART"), (409, "EMPTY_CART")]


def test_eleventh_unit_of_a_sku_is_409_quantity_limit_exceeded() -> None:
    seen = []
    for impl in ("a", "b"):
        with harness(impl) as shop:
            cart_id = shop.create_cart(CUSTOMER)
            assert shop.add_item(cart_id, "SKU-1", 10, 100).status_code == 204
            response = shop.add_item(cart_id, "SKU-1", 1, 100)
            seen.append((response.status_code, response.json()["error"]["code"]))
    assert seen == [
        (409, "QUANTITY_LIMIT_EXCEEDED"),
        (409, "QUANTITY_LIMIT_EXCEEDED"),
    ]


def test_persistence_failure_is_503_and_creates_no_order() -> None:
    seen = []
    for impl in ("a", "b"):
        with harness(impl) as shop:
            shop.client.app.dependency_overrides[deps.get_order_repository] = (
                BrokenRepository
            )
            cart_id = shop.create_cart(CUSTOMER)
            assert shop.add_item(cart_id, "SKU-1", 1, 2500).status_code == 204
            response = shop.checkout(cart_id)
            seen.append((response.status_code, response.json()["error"]["code"]))
            listing = shop.client.get(f"/customers/{CUSTOMER}/orders").json()
            assert listing["count"] == 0
    assert seen == [
        (503, "PERSISTENCE_UNAVAILABLE"),
        (503, "PERSISTENCE_UNAVAILABLE"),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"sku": "SKU-1"},
        {"sku": "SKU-1", "quantity": 0, "unit_price_cents": 100},
        {"sku": "SKU-1", "quantity": -3, "unit_price_cents": 100},
        {"sku": "", "quantity": 1, "unit_price_cents": 100},
        {"sku": "SKU-1", "quantity": 1, "unit_price_cents": -1},
        {"sku": "SKU-1", "quantity": "two", "unit_price_cents": 100},
    ],
)
def test_invalid_body_is_422_on_both_implementations(payload: dict) -> None:
    """Seul le code de statut est garanti -- pas la forme du corps.

    A renvoie la charge utile par defaut de FastAPI, B la sienne. Les deux sont
    conformes : le contrat ne garantit rien de la structure d'un 422.
    """
    for impl in ("a", "b"):
        with harness(impl) as shop:
            cart_id = shop.create_cart(CUSTOMER)
            response = shop.client.post(f"/carts/{cart_id}/items", json=payload)
            assert response.status_code == 422, (impl, payload, response.text)


def test_the_two_implementations_disagree_on_the_422_payload() -> None:
    """Documente la zone non garantie, pour qu'elle ne surprenne personne."""
    bodies = {}
    for impl in ("a", "b"):
        with harness(impl) as shop:
            cart_id = shop.create_cart(CUSTOMER)
            bodies[impl] = shop.client.post(
                f"/carts/{cart_id}/items", json={"sku": "SKU-1"}
            ).json()
    assert bodies["a"] != bodies["b"]
    assert "detail" in bodies["a"]
    assert "error" in bodies["b"]
