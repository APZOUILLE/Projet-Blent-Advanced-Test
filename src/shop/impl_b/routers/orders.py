"""Order routes of implementation B."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from shop.impl_b.models import CustomerOrdersView, OrderView
from shop.impl_b.services import CartService, get_cart_service

router = APIRouter()

_NOT_FOUND = {404: {"description": "Ressource inconnue"}}


@router.get("/orders/{order_id}", responses=_NOT_FOUND)
def read_order(
    order_id: str,
    service: CartService = Depends(get_cart_service),
) -> OrderView:
    return service.order_view(order_id)


@router.get("/customers/{customer_id}/orders")
def list_customer_orders(
    customer_id: str,
    service: CartService = Depends(get_cart_service),
) -> CustomerOrdersView:
    views = service.customer_orders(customer_id)
    return CustomerOrdersView(count=len(views), orders=views)
