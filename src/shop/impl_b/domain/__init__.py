"""Domain layer of implementation B: money, carts, coupon strategies."""

from shop.impl_b.domain.cart import Cart, CartLine, InMemoryCartStore
from shop.impl_b.domain.coupons import COUPON_REGISTRY, CouponContext
from shop.impl_b.domain.money import Money

__all__ = [
    "Cart",
    "CartLine",
    "InMemoryCartStore",
    "COUPON_REGISTRY",
    "CouponContext",
    "Money",
]
