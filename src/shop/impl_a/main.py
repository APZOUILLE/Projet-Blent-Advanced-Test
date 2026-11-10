"""Implementation A -- everything in one module, logic inside the handlers.

Carts live in `app.state.carts` as plain dictionaries, views are plain
dictionaries returned as is (extra debug keys included), money is plain `int`
cents, and coupons are an `if/elif` chain.

None of that is visible through the HTTP contract, which is the whole point of
the workshop.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from shop import deps, errors
from shop.impl_a.repository import SqliteOrderRepository
from shop.ports import Clock, IdGenerator, OrderLine, OrderRecord, OrderRepository
from shop.pricing_flag import free_shipping_threshold_cents

PARIS = ZoneInfo("Europe/Paris")

SHIPPING_FEE_CENTS = 590
MAX_QUANTITY_PER_SKU = 10

#: Coupon code -> discount percentage. Read at call time, on purpose.
PRICING_TABLE: dict[str, int] = {
    "WELCOME10": 10,
    "HAPPYHOUR": 5,
    "WEEKEND": 15,
    "NEWYEAR": 20,
}

_NOT_FOUND = {404: {"description": "Ressource inconnue"}}
_CONFLICT = {409: {"description": "Regle metier violee"}}
_UNAVAILABLE = {503: {"description": "Stockage indisponible"}}


# --------------------------------------------------------------------------
# Request bodies (the request side of the contract, identical in A and B)
# --------------------------------------------------------------------------


class CreateCartBody(BaseModel):
    customer_id: str = Field(min_length=1)


class AddItemBody(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price_cents: int = Field(ge=0)


class CouponBody(BaseModel):
    code: str = Field(min_length=1)


# --------------------------------------------------------------------------
# Real adapters
# --------------------------------------------------------------------------


class SystemClock:
    """The real clock. Returns an aware UTC datetime."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class HexIdGenerator:
    """`ORD-` + 8 lowercase hexadecimal characters."""

    def new_order_id(self) -> str:
        return "ORD-" + uuid.uuid4().hex[:8]


# --------------------------------------------------------------------------
# Pricing -- plain functions on plain ints
# --------------------------------------------------------------------------


def shipping_cents_for(payable_cents: int) -> int:
    """Return the shipping fee for an amount already net of discount."""
    if payable_cents > free_shipping_threshold_cents():
        return 0
    return SHIPPING_FEE_CENTS


def discount_cents_for(subtotal_cents: int, coupon: str | None) -> int:
    """Return the discount in cents, rounded down."""
    if coupon is None:
        return 0
    # Acces direct, sans repli : un coupon pose sur un panier a deja ete valide
    # contre cette table par `PUT /carts/{cart_id}/coupon`. S'il n'y est pas,
    # c'est un bug -- et un KeyError bruyant vaut mieux qu'une remise
    # silencieusement ramenee a zero.
    return subtotal_cents * PRICING_TABLE[coupon] // 100


def compute_cart_pricing(cart: dict[str, Any], coupon: str | None) -> dict[str, int]:
    """Price a raw internal cart dictionary. Internal helper, not a seam."""
    subtotal = sum(
        item["quantity"] * item["unit_price_cents"] for item in cart["items"].values()
    )
    discount = discount_cents_for(subtotal, coupon)
    shipping = shipping_cents_for(subtotal - discount)
    return {
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "shipping_cents": shipping,
        "total_cents": subtotal - discount + shipping,
    }


def check_coupon_is_applicable(
    code: str,
    customer_id: str,
    clock: Clock,
    repository: OrderRepository,
) -> None:
    """Raise when a coupon cannot be applied right now."""
    if code not in PRICING_TABLE:
        raise errors.UnknownCoupon("No such coupon: " + code)

    local = clock.now().astimezone(PARIS)
    if code == "WELCOME10":
        if repository.count_for_customer(customer_id) > 0:
            raise errors.CouponNotApplicable("WELCOME10 is for first orders only")
    elif code == "HAPPYHOUR":
        if not 18 <= local.hour < 20:
            raise errors.CouponNotApplicable("HAPPYHOUR runs from 18:00 to 20:00")
    elif code == "WEEKEND":
        if local.weekday() not in (5, 6):
            raise errors.CouponNotApplicable("WEEKEND runs on saturday and sunday")
    # NEWYEAR n'a pas de branche : sa borne est le 31 decembre de l'annee en
    # cours, qu'aucune date ne peut depasser. Le contrat le dit lui-meme, il est
    # toujours applicable.


# --------------------------------------------------------------------------
# Views -- raw dicts, extra keys included
# --------------------------------------------------------------------------


def cart_view(cart: dict[str, Any]) -> dict[str, Any]:
    pricing = compute_cart_pricing(cart, cart["coupon"])
    return {
        "cart_id": cart["cart_id"],
        "customer_id": cart["customer_id"],
        "lines": [dict(item) for item in cart["items"].values()],
        "coupon": cart["coupon"],
        "subtotal_cents": pricing["subtotal_cents"],
        "discount_cents": pricing["discount_cents"],
        "shipping_cents": pricing["shipping_cents"],
        "total_cents": pricing["total_cents"],
        "_debug_impl": "a",
        "raw_total": pricing["subtotal_cents"],
    }


def order_view(order: OrderRecord) -> dict[str, Any]:
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "lines": [
            {
                "sku": line.sku,
                "quantity": line.quantity,
                "unit_price_cents": line.unit_price_cents,
            }
            for line in order.lines
        ],
        "subtotal_cents": order.subtotal_cents,
        "discount_cents": order.discount_cents,
        "shipping_cents": order.shipping_cents,
        "total_cents": order.total_cents,
        "placed_at": order.placed_at.isoformat(),
        "_debug_impl": "a",
        "raw_total": order.subtotal_cents,
    }


def _cart_or_404(request: Request, cart_id: str) -> dict[str, Any]:
    cart = request.app.state.carts.get(cart_id)
    if cart is None:
        raise errors.CartNotFound("No such cart: " + cart_id)
    return cart


def _active_cart_of(request: Request, customer_id: str) -> dict[str, Any] | None:
    """Return the customer's cart in progress, if any. Linear scan, on purpose."""
    for cart in request.app.state.carts.values():
        if cart["customer_id"] == customer_id:
            return cart
    return None


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------


def create_app_a() -> FastAPI:
    """Build a fresh implementation-A application."""
    app = FastAPI(title="Shop (implementation A)", version="1.0.0")

    app.state.carts = {}
    app.state.clock = SystemClock()
    app.state.id_generator = HexIdGenerator()
    app.state.order_repository = SqliteOrderRepository(":memory:")

    errors.install_error_handlers(app)

    # The only `async def` of the repo: Starlette middleware must be async.
    # It exists so that implementation A sends a house header that B does not,
    # which makes a test asserting on it break at the swap.
    @app.middleware("http")
    async def add_impl_header(request, call_next):  # noqa: ANN001, ANN202
        response = await call_next(request)
        response.headers["X-Impl"] = "a"
        return response

    @app.post("/carts", status_code=status.HTTP_201_CREATED, responses=_CONFLICT)
    def create_cart(request: Request, body: CreateCartBody) -> JSONResponse:
        active = _active_cart_of(request, body.customer_id)
        if active is not None:
            raise errors.CartAlreadyExists(
                "This customer already has a cart in progress", active["cart_id"]
            )
        cart_id = uuid.uuid4().hex
        request.app.state.carts[cart_id] = {
            "cart_id": cart_id,
            "customer_id": body.customer_id,
            "items": {},
            "coupon": None,
        }
        return JSONResponse(
            status_code=status.HTTP_201_CREATED, content={"cart_id": cart_id}
        )

    @app.get("/carts/{cart_id}", responses=_NOT_FOUND)
    def read_cart(request: Request, cart_id: str) -> dict[str, Any]:
        return cart_view(_cart_or_404(request, cart_id))

    @app.post(
        "/carts/{cart_id}/items",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={**_NOT_FOUND, **_CONFLICT},
    )
    def add_item(request: Request, cart_id: str, body: AddItemBody) -> Response:
        cart = _cart_or_404(request, cart_id)
        existing = cart["items"].get(body.sku)
        already = existing["quantity"] if existing else 0
        if already + body.quantity > MAX_QUANTITY_PER_SKU:
            raise errors.QuantityLimitExceeded(
                "At most 10 units per sku, asked for " + str(already + body.quantity)
            )
        cart["items"][body.sku] = {
            "sku": body.sku,
            "quantity": already + body.quantity,
            "unit_price_cents": body.unit_price_cents,
        }
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.delete(
        "/carts/{cart_id}/items/{sku}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses=_NOT_FOUND,
    )
    def remove_item(request: Request, cart_id: str, sku: str) -> Response:
        cart = _cart_or_404(request, cart_id)
        cart["items"].pop(sku, None)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.put(
        "/carts/{cart_id}/coupon",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={**_NOT_FOUND, **_CONFLICT},
    )
    def set_coupon(
        request: Request,
        cart_id: str,
        body: CouponBody,
        clock: Clock = Depends(deps.get_clock),
        repository: OrderRepository = Depends(deps.get_order_repository),
    ) -> Response:
        cart = _cart_or_404(request, cart_id)
        check_coupon_is_applicable(body.code, cart["customer_id"], clock, repository)
        cart["coupon"] = body.code
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/carts/{cart_id}/checkout",
        status_code=status.HTTP_201_CREATED,
        responses={**_NOT_FOUND, **_CONFLICT, **_UNAVAILABLE},
    )
    def checkout(
        request: Request,
        cart_id: str,
        clock: Clock = Depends(deps.get_clock),
        ids: IdGenerator = Depends(deps.get_id_generator),
        repository: OrderRepository = Depends(deps.get_order_repository),
    ) -> JSONResponse:
        cart = _cart_or_404(request, cart_id)
        if not cart["items"]:
            raise errors.EmptyCart("Cart is empty")

        pricing = compute_cart_pricing(cart, cart["coupon"])
        order = OrderRecord(
            order_id=ids.new_order_id(),
            customer_id=cart["customer_id"],
            lines=tuple(
                OrderLine(
                    sku=item["sku"],
                    quantity=item["quantity"],
                    unit_price_cents=item["unit_price_cents"],
                )
                for item in cart["items"].values()
            ),
            subtotal_cents=pricing["subtotal_cents"],
            discount_cents=pricing["discount_cents"],
            shipping_cents=pricing["shipping_cents"],
            total_cents=pricing["total_cents"],
            placed_at=clock.now(),
        )
        repository.save(order)
        # The order carries its own copy of the lines: once it is persisted the
        # cart has no reason to survive. Deleting it here -- and only here, after
        # a successful save -- is what keeps one cart per customer true.
        del request.app.state.carts[cart_id]
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=order_view(order),
            headers={"Location": "/orders/" + order.order_id},
        )

    @app.get("/orders/{order_id}", responses=_NOT_FOUND)
    def read_order(
        order_id: str,
        repository: OrderRepository = Depends(deps.get_order_repository),
    ) -> dict[str, Any]:
        order = repository.get(order_id)
        if order is None:
            raise errors.OrderNotFound("No such order: " + order_id)
        return order_view(order)

    @app.get("/customers/{customer_id}/orders")
    def list_customer_orders(
        customer_id: str,
        repository: OrderRepository = Depends(deps.get_order_repository),
    ) -> dict[str, Any]:
        orders = repository.list_for_customer(customer_id)
        return {"count": len(orders), "orders": [order_view(order) for order in orders]}

    @app.get("/_internal/state", include_in_schema=False)
    def internal_state(request: Request) -> dict[str, Any]:
        """Debug window on the in-memory carts. Not part of the contract."""
        return {"carts": request.app.state.carts}

    return app
