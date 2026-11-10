"""A et B produisent les memes montants, au centime. FOURNI -- NE PAS MODIFIER.

Si ce fichier casse, ce n'est pas ton test qui est en cause : c'est le repo.
"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import AMOUNT_FIELDS, Harness, harness
from scenarios import SCENARIOS, Scenario

CUSTOMER = "contract-customer"


def _replay(impl: str, scenario: Scenario) -> dict[str, Any]:
    """Rejoue un scenario de bout en bout et renvoie ce que le contrat garantit."""
    with harness(impl, scenario.instant) as shop:
        if scenario.prior_order:
            _place_a_prior_order(shop)

        cart_id = shop.create_cart(CUSTOMER)
        for item in scenario.items:
            response = shop.add_item(
                cart_id, item.sku, item.quantity, item.unit_price_cents
            )
            assert response.status_code == 204, response.text
        for sku in scenario.removals:
            response = shop.client.delete(f"/carts/{cart_id}/items/{sku}")
            assert response.status_code == 204, response.text

        coupon_status = None
        if scenario.coupon is not None:
            coupon_response = shop.set_coupon(cart_id, scenario.coupon)
            coupon_status = coupon_response.status_code

        cart = shop.cart(cart_id).json()
        checkout = shop.checkout(cart_id)
        order = checkout.json()

        return {
            "coupon_status": coupon_status,
            "cart_coupon": cart["coupon"],
            "cart_amounts": {field: cart[field] for field in AMOUNT_FIELDS},
            "cart_lines": sorted(
                (line["sku"], line["quantity"], line["unit_price_cents"])
                for line in cart["lines"]
            ),
            "checkout_status": checkout.status_code,
            "order_amounts": {field: order[field] for field in AMOUNT_FIELDS},
            "order_lines": sorted(
                (line["sku"], line["quantity"], line["unit_price_cents"])
                for line in order["lines"]
            ),
            "customer_count": shop.client.get(f"/customers/{CUSTOMER}/orders").json()[
                "count"
            ],
        }


def _place_a_prior_order(shop: Harness) -> None:
    """Fait passer une vraie commande au meme client, via l'API."""
    cart_id = shop.create_cart(CUSTOMER)
    assert shop.add_item(cart_id, "SKU-PAST", 1, 1000).status_code == 204
    assert shop.checkout(cart_id).status_code == 201


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_both_implementations_agree_to_the_cent(scenario: Scenario) -> None:
    observed_a = _replay("a", scenario)
    observed_b = _replay("b", scenario)
    assert observed_a == observed_b


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_coupon_status_matches_the_scenario(scenario: Scenario) -> None:
    """Le scenario declare le code attendu au PUT : les deux apps le respectent."""
    for impl in ("a", "b"):
        observed = _replay(impl, scenario)
        if scenario.coupon is None:
            assert observed["coupon_status"] is None
        else:
            assert observed["coupon_status"] == scenario.coupon_status, impl


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_total_is_subtotal_minus_discount_plus_shipping(scenario: Scenario) -> None:
    """Invariant arithmetique, verifie sur chaque scenario et chaque app."""
    for impl in ("a", "b"):
        amounts = _replay(impl, scenario)["order_amounts"]
        expected = (
            amounts["subtotal_cents"]
            - amounts["discount_cents"]
            + amounts["shipping_cents"]
        )
        assert amounts["total_cents"] == expected, impl
