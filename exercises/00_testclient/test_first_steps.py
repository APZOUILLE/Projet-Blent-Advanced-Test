"""Module 0 -- TestClient et injection de dependances.

Trois exemples complets, deux tests a ecrire toi-meme.

Ce que je suggère : **une application neuve par test**. Construite par
`create_app()`, jamais importee toute faite depuis `shop`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from shop import create_app, deps

PARIS = ZoneInfo("Europe/Paris")


@dataclass(frozen=True)
class FixedClock:
    """Horloge figee. Renvoie toujours le meme instant, timezone-aware."""

    instant: datetime

    def now(self) -> datetime:
        return self.instant


# ---------------------------------------------------------------------------
# Exemple 1 : un premier test, de bout en bout, par les routes
# ---------------------------------------------------------------------------


def test_a_new_cart_is_empty() -> None:
    client = TestClient(create_app())

    created = client.post("/carts", json={"customer_id": "alice"})
    assert created.status_code == 201

    cart_id = created.json()["cart_id"]
    cart = client.get(f"/carts/{cart_id}")

    assert cart.status_code == 200
    body = cart.json()
    assert body["customer_id"] == "alice"
    assert body["lines"] == []
    assert body["subtotal_cents"] == 0
    assert body["discount_cents"] == 0
    assert body["coupon"] is None


# ---------------------------------------------------------------------------
# A toi : deux tests a ecrire, en passant uniquement par les routes
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="TODO module 0 : a ecrire (voir exercises/00_testclient/ENONCE.md)")
def test_adding_an_item_shows_up_in_the_cart() -> None:
    """Ajoute une ligne a un panier, puis verifie ce que renvoie GET /carts/{id}.

    Attendu : 2 unites a 1500 centimes donnent un sous-total de 3000 centimes.
    """
    raise NotImplementedError


@pytest.mark.skip(reason="TODO module 0 : a ecrire (voir exercises/00_testclient/ENONCE.md)")
def test_checking_out_an_empty_cart_is_refused() -> None:
    """Un checkout sur un panier vide renvoie 409 et le code EMPTY_CART.

    Assert sur le code de statut et sur `body["error"]["code"]`.
    Surtout pas sur `body["error"]["message"]` : c'est de la prose.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Exemple 2 : surcharger une dependance
# ---------------------------------------------------------------------------


def test_the_clock_can_be_replaced_for_one_application() -> None:
    """`app.dependency_overrides` remplace un provider par un autre callable.

    La cle est le provider lui-meme (`deps.get_clock`), pas son nom. C'est
    pour cela que `shop/deps.py` est partage par les deux implementations.

    L'application est locale a ce test : rien a nettoyer, rien qui fuit.
    """
    app = create_app()
    instant = datetime(2026, 3, 14, 18, 30, tzinfo=PARIS)  # un samedi, 18h30
    app.dependency_overrides[deps.get_clock] = lambda: FixedClock(instant)
    client = TestClient(app)

    cart_id = client.post("/carts", json={"customer_id": "bob"}).json()["cart_id"]
    client.post(
        f"/carts/{cart_id}/items",
        json={"sku": "SKU-1", "quantity": 1, "unit_price_cents": 2000},
    )
    order = client.post(f"/carts/{cart_id}/checkout").json()

    assert datetime.fromisoformat(order["placed_at"]) == instant


def test_the_frozen_clock_also_drives_the_business_rules() -> None:
    """Une horloge figee n'est pas un decor : elle change la decision metier.

    Le 14 mars 2026 est un samedi : WEEKEND s'applique. Le 10 mars 2026 est un
    mardi : le meme coupon est refuse. Rien d'autre ne change entre les deux.
    """
    saturday = datetime(2026, 3, 14, 18, 30, tzinfo=PARIS)
    tuesday = datetime(2026, 3, 10, 18, 30, tzinfo=PARIS)

    assert _coupon_status_at(saturday, "WEEKEND") == 204
    assert _coupon_status_at(tuesday, "WEEKEND") == 409


def _coupon_status_at(instant: datetime, code: str) -> int:
    """Applique un coupon sur une application neuve, horloge figee."""
    app = create_app()
    app.dependency_overrides[deps.get_clock] = lambda: FixedClock(instant)
    client = TestClient(app)
    cart_id = client.post("/carts", json={"customer_id": "carol"}).json()["cart_id"]
    return client.put(f"/carts/{cart_id}/coupon", json={"code": code}).status_code
