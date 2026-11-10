"""Cycle de vie du panier, identique sur A et sur B. FOURNI -- NE PAS MODIFIER.

Un client a au plus un panier en cours ; un checkout reussi le supprime ; un
checkout qui echoue n'y touche pas.
"""

from __future__ import annotations

import pytest
from conftest import harness

from shop import deps
from shop.errors import PersistenceUnavailable
from shop.ports import OrderRecord

CUSTOMER = "lifecycle-customer"


class BrokenRepository:
    """Depot dont l'ecriture echoue toujours (pour atteindre le 503)."""

    def save(self, order: OrderRecord) -> None:
        raise PersistenceUnavailable("disk on fire")

    def get(self, order_id: str):
        return None

    def list_for_customer(self, customer_id: str):
        return []

    def count_for_customer(self, customer_id: str) -> int:
        return 0


@pytest.mark.parametrize("impl", ["a", "b"])
def test_a_second_cart_for_the_same_customer_is_refused(impl: str) -> None:
    with harness(impl) as shop:
        first = shop.create_cart(CUSTOMER)

        response = shop.client.post("/carts", json={"customer_id": CUSTOMER})

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CART_ALREADY_EXISTS"


@pytest.mark.parametrize("impl", ["a", "b"])
def test_the_refusal_hands_back_the_existing_cart(impl: str) -> None:
    """Sans cet identifiant, le client serait enferme hors de son panier."""
    with harness(impl) as shop:
        existing = shop.create_cart(CUSTOMER)

        response = shop.client.post("/carts", json={"customer_id": CUSTOMER})

        assert response.json()["error"]["cart_id"] == existing
        assert response.headers["Location"] == f"/carts/{existing}"
        # Et l'identifiant rendu est reellement utilisable.
        assert shop.client.get(response.headers["Location"]).status_code == 200


@pytest.mark.parametrize("impl", ["a", "b"])
def test_two_customers_have_two_distinct_carts(impl: str) -> None:
    with harness(impl) as shop:
        first = shop.create_cart("customer-one")
        second = shop.create_cart("customer-two")

    assert first != second


@pytest.mark.parametrize("impl", ["a", "b"])
def test_a_successful_checkout_deletes_the_cart(impl: str) -> None:
    with harness(impl) as shop:
        cart_id = shop.create_cart(CUSTOMER)
        assert shop.add_item(cart_id, "SKU-1", 1, 2500).status_code == 204
        assert shop.checkout(cart_id).status_code == 201

        gone = shop.cart(cart_id)
        assert gone.status_code == 404
        assert gone.json()["error"]["code"] == "CART_NOT_FOUND"


@pytest.mark.parametrize("impl", ["a", "b"])
def test_a_second_checkout_finds_no_cart(impl: str) -> None:
    with harness(impl) as shop:
        cart_id = shop.create_cart(CUSTOMER)
        shop.add_item(cart_id, "SKU-1", 1, 2500)
        assert shop.checkout(cart_id).status_code == 201

        again = shop.checkout(cart_id)

        assert again.status_code == 404
        assert again.json()["error"]["code"] == "CART_NOT_FOUND"
        # Une seule commande a ete creee.
        assert shop.client.get(f"/customers/{CUSTOMER}/orders").json()["count"] == 1


@pytest.mark.parametrize("impl", ["a", "b"])
def test_the_customer_can_open_a_new_cart_after_a_checkout(impl: str) -> None:
    with harness(impl) as shop:
        first = shop.create_cart(CUSTOMER)
        shop.add_item(first, "SKU-1", 1, 2500)
        assert shop.checkout(first).status_code == 201

        second = shop.create_cart(CUSTOMER)

    assert second != first


@pytest.mark.parametrize("impl", ["a", "b"])
def test_a_refused_checkout_leaves_the_cart_intact(impl: str) -> None:
    """409 EMPTY_CART : le panier vide est toujours la, et toujours ouvrable."""
    with harness(impl) as shop:
        cart_id = shop.create_cart(CUSTOMER)

        assert shop.checkout(cart_id).status_code == 409
        assert shop.cart(cart_id).status_code == 200
        # Le client a donc toujours un panier en cours.
        assert shop.client.post("/carts", json={"customer_id": CUSTOMER}).status_code == 409


@pytest.mark.parametrize("impl", ["a", "b"])
def test_a_failed_persistence_leaves_the_cart_intact(impl: str) -> None:
    """503 PERSISTENCE_UNAVAILABLE : rien n'est perdu, le panier est reutilisable."""
    with harness(impl) as shop:
        shop.client.app.dependency_overrides[deps.get_order_repository] = BrokenRepository
        cart_id = shop.create_cart(CUSTOMER)
        shop.add_item(cart_id, "SKU-1", 2, 1500)

        assert shop.checkout(cart_id).status_code == 503

        cart = shop.cart(cart_id)
        assert cart.status_code == 200
        assert cart.json()["subtotal_cents"] == 3000
