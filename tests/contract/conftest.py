"""Outillage des tests de contrat. FOURNI -- NE PAS MODIFIER.

Ces tests sont les seuls du repo autorises a connaitre les deux
implementations : leur travail est justement de prouver qu'elles sont
interchangeables. Tout le reste du repo passe par `shop.create_app()`.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from shop import build_app, build_order_repository

PARIS = ZoneInfo("Europe/Paris")
IMPLEMENTATIONS = ("a", "b")

#: Champs garantis par le contrat (docs/CONTRAT_HTTP.md).
CART_FIELDS = (
    "cart_id",
    "customer_id",
    "lines",
    "coupon",
    "subtotal_cents",
    "discount_cents",
    "shipping_cents",
    "total_cents",
)
ORDER_FIELDS = (
    "order_id",
    "customer_id",
    "lines",
    "subtotal_cents",
    "discount_cents",
    "shipping_cents",
    "total_cents",
    "placed_at",
)
LINE_FIELDS = ("sku", "quantity", "unit_price_cents")
AMOUNT_FIELDS = (
    "subtotal_cents",
    "discount_cents",
    "shipping_cents",
    "total_cents",
)


@dataclass(frozen=True)
class FixedClock:
    """Horloge figee, timezone-aware."""

    instant: datetime

    def now(self) -> datetime:
        return self.instant


@dataclass
class Harness:
    """Une application, son client, et de quoi rejouer un scenario."""

    impl: str
    client: TestClient

    def create_cart(self, customer_id: str) -> str:
        response = self.client.post("/carts", json={"customer_id": customer_id})
        assert response.status_code == 201, response.text
        return response.json()["cart_id"]

    def add_item(self, cart_id: str, sku: str, quantity: int, price: int):
        return self.client.post(
            f"/carts/{cart_id}/items",
            json={"sku": sku, "quantity": quantity, "unit_price_cents": price},
        )

    def set_coupon(self, cart_id: str, code: str):
        return self.client.put(f"/carts/{cart_id}/coupon", json={"code": code})

    def checkout(self, cart_id: str):
        return self.client.post(f"/carts/{cart_id}/checkout")

    def cart(self, cart_id: str):
        return self.client.get(f"/carts/{cart_id}")


@contextmanager
def harness(impl: str, instant: datetime | None = None) -> Iterator[Harness]:
    """Construit une application neuve pour `impl`, horloge eventuellement figee."""
    from shop import deps

    app = build_app(impl)
    app.state.order_repository = build_order_repository(impl, ":memory:")
    if instant is not None:
        app.dependency_overrides[deps.get_clock] = lambda: FixedClock(instant)
    with TestClient(app) as client:
        yield Harness(impl=impl, client=client)
    app.dependency_overrides.clear()
