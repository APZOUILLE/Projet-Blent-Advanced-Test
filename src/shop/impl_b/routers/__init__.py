"""HTTP layer of implementation B: anemic handlers, one router per resource."""

from shop.impl_b.routers import carts, orders

__all__ = ["carts", "orders"]
