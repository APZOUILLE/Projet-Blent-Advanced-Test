"""Ports of the shop application: the seams every implementation shares.

A "port" here is a `Protocol`: a structural contract. Any object with the right
methods can be plugged in, which is exactly what makes test doubles possible
without inheritance.

Both implementations (A and B) depend on *these* protocols and on the providers
of `shop.deps` -- never on each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class OrderLine:
    """One line of a placed order, as it crosses the repository boundary."""

    sku: str
    quantity: int
    unit_price_cents: int


@dataclass(frozen=True)
class OrderRecord:
    """The neutral shape of a placed order, shared by every implementation.

    Implementations A and B model carts and money very differently on the
    inside, but they both hand *this* record to an `OrderRepository`. That is
    what lets a single test double work against either implementation.
    """

    order_id: str
    customer_id: str
    lines: tuple[OrderLine, ...]
    subtotal_cents: int
    discount_cents: int
    shipping_cents: int
    total_cents: int
    placed_at: datetime


@runtime_checkable
class Clock(Protocol):
    """Source of the current instant.

    Implementations MUST return a timezone-aware `datetime`. Coupon rules are
    evaluated in Europe/Paris, so a naive datetime would silently change the
    business outcome.
    """

    def now(self) -> datetime:
        """Return the current instant, timezone-aware."""


@runtime_checkable
class IdGenerator(Protocol):
    """Source of order identifiers."""

    def new_order_id(self) -> str:
        """Return a fresh order id. Opaque, prefixed with `ORD-`, <= 32 chars."""


@runtime_checkable
class OrderRepository(Protocol):
    """Persistence port for placed orders.

    Any method of any implementation MAY raise
    `shop.errors.PersistenceUnavailable` when the underlying storage cannot be
    reached. Callers turn that into `503 PERSISTENCE_UNAVAILABLE`; see
    `docs/CONTRAT_HTTP.md`.
    """

    def save(self, order: OrderRecord) -> None:
        """Persist a placed order.

        Raises:
            shop.errors.PersistenceUnavailable: storage is unreachable.
        """

    def get(self, order_id: str) -> OrderRecord | None:
        """Return the stored order, or `None` when it does not exist."""

    def list_for_customer(self, customer_id: str) -> list[OrderRecord]:
        """Return every order of a customer. The order of the list is NOT part
        of the HTTP contract."""

    def count_for_customer(self, customer_id: str) -> int:
        """Return how many orders a customer has already placed."""
