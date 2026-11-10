"""Service layer of implementation B: the handlers delegate everything here."""

from shop.impl_b.services.cart_service import CartService, get_cart_service

__all__ = ["CartService", "get_cart_service"]
