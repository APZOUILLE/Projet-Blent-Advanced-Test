"""Cart aggregate of implementation B.

Carts are objects with behaviour, kept in a store that the application owns.
Implementation A keeps raw dictionaries in `app.state.carts` instead -- a test
that reaches for that attribute is reaching for an implementation detail.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from shop import errors
from shop.impl_b.domain.money import Money

MAX_QUANTITY_PER_SKU = 10


@dataclass
class CartLine:
    sku: str
    quantity: int
    unit_price: Money

    def subtotal(self) -> Money:
        return self.unit_price.times(self.quantity)


@dataclass
class Cart:
    cart_id: str
    customer_id: str
    lines: dict[str, CartLine] = field(default_factory=dict)
    coupon: str | None = None

    def add(self, sku: str, quantity: int, unit_price: Money) -> None:
        """Add units of a sku, cumulating with what is already there."""
        line = self.lines.get(sku)
        already = line.quantity if line is not None else 0
        wanted = already + quantity
        if wanted > MAX_QUANTITY_PER_SKU:
            raise errors.QuantityLimitExceeded(
                "This basket cannot hold more than 10 units of the same product"
            )
        self.lines[sku] = CartLine(sku=sku, quantity=wanted, unit_price=unit_price)

    def remove(self, sku: str) -> None:
        self.lines.pop(sku, None)

    def is_empty(self) -> bool:
        return not self.lines

    def sorted_lines(self) -> list[CartLine]:
        """Lines sorted by sku. The contract does not guarantee any order."""
        return [self.lines[sku] for sku in sorted(self.lines)]

    def subtotal(self) -> Money:
        total = Money.zero()
        for line in self.lines.values():
            total = total + line.subtotal()
        return total


class InMemoryCartStore:
    """Holds the carts of one application instance, indexed by customer too.

    A customer has at most one cart in progress; the index makes that invariant
    cheap to enforce and impossible to forget.
    """

    def __init__(self) -> None:
        self._carts: dict[str, Cart] = {}
        self._by_customer: dict[str, str] = {}

    def create(self, customer_id: str) -> Cart:
        cart = Cart(cart_id=uuid.uuid4().hex, customer_id=customer_id)
        self._carts[cart.cart_id] = cart
        self._by_customer[customer_id] = cart.cart_id
        return cart

    def find_for_customer(self, customer_id: str) -> Cart | None:
        """Return the customer's cart in progress, or `None`."""
        cart_id = self._by_customer.get(customer_id)
        return None if cart_id is None else self._carts.get(cart_id)

    def require(self, cart_id: str) -> Cart:
        cart = self._carts.get(cart_id)
        if cart is None:
            raise errors.CartNotFound("Unknown basket identifier " + cart_id)
        return cart

    def discard(self, cart_id: str) -> None:
        """Drop a cart once its order has been placed."""
        cart = self._carts.pop(cart_id, None)
        if cart is not None:
            self._by_customer.pop(cart.customer_id, None)
