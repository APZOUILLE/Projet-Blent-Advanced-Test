"""Test de sanite des providers partages. FOURNI -- NE PAS MODIFIER.

Si ce fichier casse, **tout le repo est casse** : cela veut dire qu'une
implementation a redefini ses propres providers au lieu d'importer ceux de
`shop.deps`, et que les surcharges ecrites par les participants ne
s'appliquent plus apres le swap -- silencieusement.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from conftest import PARIS, FixedClock
from fastapi.testclient import TestClient

from shop import build_app, deps
from shop.ports import OrderRecord

REFERENCE_INSTANT = datetime(2026, 3, 14, 18, 30, tzinfo=PARIS)
CUSTOMER = "sanity-customer"


class CountingIdGenerator:
    """Generateur d'identifiants previsible, pour ce test de sanite uniquement."""

    def __init__(self) -> None:
        self.calls = 0

    def new_order_id(self) -> str:
        self.calls += 1
        return "ORD-SANITY-" + str(self.calls)


class RecordingRepository:
    """Depot qui enregistre ce qu'on lui demande de sauvegarder."""

    def __init__(self) -> None:
        self.saved: list[OrderRecord] = []

    def save(self, order: OrderRecord) -> None:
        self.saved.append(order)

    def get(self, order_id: str) -> OrderRecord | None:
        return next((o for o in self.saved if o.order_id == order_id), None)

    def list_for_customer(self, customer_id: str) -> list[OrderRecord]:
        return [o for o in self.saved if o.customer_id == customer_id]

    def count_for_customer(self, customer_id: str) -> int:
        return len(self.list_for_customer(customer_id))


@pytest.mark.parametrize("impl", ["a", "b"])
def test_overriding_get_clock_changes_the_observed_placed_at(impl: str) -> None:
    app = build_app(impl)
    app.dependency_overrides[deps.get_clock] = lambda: FixedClock(REFERENCE_INSTANT)
    with TestClient(app) as client:
        cart_id = client.post("/carts", json={"customer_id": CUSTOMER}).json()["cart_id"]
        client.post(
            f"/carts/{cart_id}/items",
            json={"sku": "SKU-1", "quantity": 1, "unit_price_cents": 2000},
        )
        order = client.post(f"/carts/{cart_id}/checkout").json()

    observed = datetime.fromisoformat(order["placed_at"])
    assert observed == REFERENCE_INSTANT
    assert observed.astimezone(timezone.utc) == REFERENCE_INSTANT.astimezone(
        timezone.utc
    )


@pytest.mark.parametrize("impl", ["a", "b"])
def test_overriding_get_clock_changes_coupon_applicability(impl: str) -> None:
    """La surcharge doit atteindre la regle metier, pas seulement l'affichage."""
    app = build_app(impl)
    app.dependency_overrides[deps.get_clock] = lambda: FixedClock(REFERENCE_INSTANT)
    with TestClient(app) as client:
        cart_id = client.post("/carts", json={"customer_id": CUSTOMER}).json()["cart_id"]
        # 14 mars 2026 est un samedi, a 18h30 : WEEKEND et HAPPYHOUR passent.
        assert client.put(f"/carts/{cart_id}/coupon", json={"code": "WEEKEND"}).status_code == 204
        assert client.put(f"/carts/{cart_id}/coupon", json={"code": "HAPPYHOUR"}).status_code == 204


@pytest.mark.parametrize("impl", ["a", "b"])
def test_overriding_get_id_generator_changes_the_observed_order_id(impl: str) -> None:
    app = build_app(impl)
    generator = CountingIdGenerator()
    app.dependency_overrides[deps.get_id_generator] = lambda: generator
    with TestClient(app) as client:
        cart_id = client.post("/carts", json={"customer_id": CUSTOMER}).json()["cart_id"]
        client.post(
            f"/carts/{cart_id}/items",
            json={"sku": "SKU-1", "quantity": 1, "unit_price_cents": 2000},
        )
        order = client.post(f"/carts/{cart_id}/checkout").json()

    assert order["order_id"] == "ORD-SANITY-1"
    assert generator.calls == 1


@pytest.mark.parametrize("impl", ["a", "b"])
def test_overriding_get_order_repository_captures_the_saved_order(impl: str) -> None:
    app = build_app(impl)
    repository = RecordingRepository()
    app.dependency_overrides[deps.get_order_repository] = lambda: repository
    with TestClient(app) as client:
        cart_id = client.post("/carts", json={"customer_id": CUSTOMER}).json()["cart_id"]
        client.post(
            f"/carts/{cart_id}/items",
            json={"sku": "SKU-1", "quantity": 2, "unit_price_cents": 2000},
        )
        order = client.post(f"/carts/{cart_id}/checkout").json()

    assert len(repository.saved) == 1
    assert repository.saved[0].order_id == order["order_id"]
    assert repository.saved[0].total_cents == order["total_cents"]


def _providers_reachable_from(app) -> set:
    """Tous les callables de dependance atteignables depuis les routes."""

    def walk(dependant, seen: set) -> None:
        for dependency in dependant.dependencies:
            seen.add(dependency.call)
            walk(dependency, seen)

    seen: set = set()
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is not None:
            walk(dependant, seen)
    return seen


@pytest.mark.parametrize("impl", ["a", "b"])
def test_the_three_providers_are_the_very_same_callables_in_both_apps(impl: str) -> None:
    """Le coeur du dispositif : les cles des surcharges sont partagees.

    Une implementation peut tres bien avoir ses propres providers locaux -- B en
    a un, `get_cart_service` -- du moment qu'ils sont construits *au-dessus* de
    ceux de `shop.deps`, qui restent donc atteignables.
    """
    reachable = _providers_reachable_from(build_app(impl))
    assert deps.get_clock in reachable, impl
    assert deps.get_id_generator in reachable, impl
    assert deps.get_order_repository in reachable, impl
