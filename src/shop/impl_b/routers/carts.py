"""Cart routes of implementation B. Every handler is one line of delegation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from shop.impl_b.models import (
    AddItemPayload,
    CartCreated,
    CartView,
    CouponPayload,
    CreateCartPayload,
    OrderView,
)
from shop.impl_b.services import CartService, get_cart_service

router = APIRouter()

_NOT_FOUND = {404: {"description": "Ressource inconnue"}}
_CONFLICT = {409: {"description": "Regle metier violee"}}
_UNAVAILABLE = {503: {"description": "Stockage indisponible"}}


@router.post("/carts", status_code=status.HTTP_201_CREATED, responses=_CONFLICT)
def create_cart(
    payload: CreateCartPayload,
    service: CartService = Depends(get_cart_service),
) -> CartCreated:
    return CartCreated(cart_id=service.create_cart(payload.customer_id))


@router.get("/carts/{cart_id}", responses=_NOT_FOUND)
def read_cart(
    cart_id: str,
    service: CartService = Depends(get_cart_service),
) -> CartView:
    return service.cart_view(cart_id)


@router.post(
    "/carts/{cart_id}/items",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_NOT_FOUND, **_CONFLICT},
)
def add_item(
    cart_id: str,
    payload: AddItemPayload,
    service: CartService = Depends(get_cart_service),
) -> Response:
    service.add_item(cart_id, payload.sku, payload.quantity, payload.unit_price_cents)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/carts/{cart_id}/items/{sku}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_NOT_FOUND,
)
def remove_item(
    cart_id: str,
    sku: str,
    service: CartService = Depends(get_cart_service),
) -> Response:
    service.remove_item(cart_id, sku)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/carts/{cart_id}/coupon",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_NOT_FOUND, **_CONFLICT},
)
def set_coupon(
    cart_id: str,
    payload: CouponPayload,
    service: CartService = Depends(get_cart_service),
) -> Response:
    service.set_coupon(cart_id, payload.code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/carts/{cart_id}/checkout",
    status_code=status.HTTP_201_CREATED,
    responses={**_NOT_FOUND, **_CONFLICT, **_UNAVAILABLE},
)
def checkout(
    cart_id: str,
    response: Response,
    service: CartService = Depends(get_cart_service),
) -> OrderView:
    view = service.checkout(cart_id)
    response.headers["Location"] = "/orders/" + view.order_id
    return view
