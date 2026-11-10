"""Application service of implementation B.

The handlers in `shop.impl_b.routers` do nothing but call these methods and
return their result. All the business decisions live here.

Note how the service receives its collaborators -- clock, id generator,
repository -- through the *shared* providers of `shop.deps`. A test that
overrides `shop.deps.get_clock` reaches this service without knowing it exists.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, Request

from shop import deps, errors
from shop.impl_b.domain.cart import Cart, InMemoryCartStore
from shop.impl_b.domain.coupons import COUPON_REGISTRY, CouponContext
from shop.impl_b.domain.money import Money
from shop.impl_b.models import CartView, LineView, OrderView
from shop.ports import Clock, IdGenerator, OrderLine, OrderRecord, OrderRepository
from shop.pricing_flag import free_shipping_threshold_cents

PARIS = ZoneInfo("Europe/Paris")
SHIPPING_FEE = Money(590)


def shipping_for(payable: Money) -> Money:
    """Return the shipping fee for an amount already net of discount."""
    if payable > Money(free_shipping_threshold_cents()):
        return Money.zero()
    return SHIPPING_FEE


def discount_for(subtotal: Money, coupon_code: str | None) -> Money:
    """Return the discount, rounded down to the cent."""
    if coupon_code is None:
        return Money.zero()
    return subtotal.percentage(COUPON_REGISTRY[coupon_code].percent)


class CartService:
    """Everything the shop can do with a basket."""

    def __init__(
        self,
        store: InMemoryCartStore,
        clock: Clock,
        ids: IdGenerator,
        repository: OrderRepository,
    ) -> None:
        self._store = store
        self._clock = clock
        self._ids = ids
        self._repository = repository

    # -- commands ---------------------------------------------------------

    def create_cart(self, customer_id: str) -> str:
        in_progress = self._store.find_for_customer(customer_id)
        if in_progress is not None:
            raise errors.CartAlreadyExists(
                "A basket is already open for this customer", in_progress.cart_id
            )
        return self._store.create(customer_id).cart_id

    def add_item(
        self, cart_id: str, sku: str, quantity: int, unit_price_cents: int
    ) -> None:
        self._store.require(cart_id).add(sku, quantity, Money(unit_price_cents))

    def remove_item(self, cart_id: str, sku: str) -> None:
        self._store.require(cart_id).remove(sku)

    def set_coupon(self, cart_id: str, code: str) -> None:
        cart = self._store.require(cart_id)
        coupon = COUPON_REGISTRY.get(code)
        if coupon is None:
            raise errors.UnknownCoupon("Coupon " + code + " does not exist")
        context = CouponContext(
            customer_id=cart.customer_id,
            local_now=self._local_now(),
            orders_already_placed=self._repository.count_for_customer(cart.customer_id),
        )
        if not coupon.applies(context):
            raise errors.CouponNotApplicable(coupon.refusal)
        cart.coupon = code

    def checkout(self, cart_id: str) -> OrderView:
        cart = self._store.require(cart_id)
        if cart.is_empty():
            raise errors.EmptyCart("Cannot check out an empty cart")

        subtotal = cart.subtotal()
        discount = discount_for(subtotal, cart.coupon)
        shipping = shipping_for(subtotal - discount)
        placed_at = self._clock.now()
        record = OrderRecord(
            order_id=self._ids.new_order_id(),
            customer_id=cart.customer_id,
            lines=tuple(
                OrderLine(
                    sku=line.sku,
                    quantity=line.quantity,
                    unit_price_cents=line.unit_price.cents,
                )
                for line in cart.sorted_lines()
            ),
            subtotal_cents=subtotal.cents,
            discount_cents=discount.cents,
            shipping_cents=shipping.cents,
            total_cents=(subtotal - discount + shipping).cents,
            placed_at=placed_at,
        )
        self._repository.save(record)
        # Only once the order is safely persisted: the basket has served its
        # purpose, and the customer is free to open a new one.
        self._store.discard(cart_id)
        return order_view(record)

    # -- queries ----------------------------------------------------------

    def cart_view(self, cart_id: str) -> CartView:
        cart = self._store.require(cart_id)
        subtotal = cart.subtotal()
        discount = discount_for(subtotal, cart.coupon)
        shipping = shipping_for(subtotal - discount)
        return CartView(
            cart_id=cart.cart_id,
            customer_id=cart.customer_id,
            lines=[_line_view(line) for line in cart.sorted_lines()],
            coupon=cart.coupon,
            subtotal_cents=subtotal.cents,
            discount_cents=discount.cents,
            shipping_cents=shipping.cents,
            total_cents=(subtotal - discount + shipping).cents,
        )

    def order_view(self, order_id: str) -> OrderView:
        record = self._repository.get(order_id)
        if record is None:
            raise errors.OrderNotFound("Order " + order_id + " is not in the store")
        return order_view(record)

    def customer_orders(self, customer_id: str) -> list[OrderView]:
        return [
            order_view(record)
            for record in self._repository.list_for_customer(customer_id)
        ]

    # -- helpers ----------------------------------------------------------

    def _local_now(self) -> datetime:
        return self._clock.now().astimezone(PARIS)


def _line_view(line) -> LineView:  # noqa: ANN001 - domain type, kept private
    return LineView(
        sku=line.sku, quantity=line.quantity, unit_price_cents=line.unit_price.cents
    )


def order_view(record: OrderRecord) -> OrderView:
    return OrderView(
        order_id=record.order_id,
        customer_id=record.customer_id,
        lines=[
            LineView(
                sku=line.sku,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
            )
            for line in sorted(record.lines, key=lambda line: line.sku)
        ],
        subtotal_cents=record.subtotal_cents,
        discount_cents=record.discount_cents,
        shipping_cents=record.shipping_cents,
        total_cents=record.total_cents,
        placed_at=record.placed_at.isoformat(),
    )


def get_cart_service(
    request: Request,
    clock: Clock = Depends(deps.get_clock),
    ids: IdGenerator = Depends(deps.get_id_generator),
    repository: OrderRepository = Depends(deps.get_order_repository),
) -> CartService:
    """Assemble a service for the current request.

    This provider is private to implementation B; it is built *on top of* the
    shared providers, so overriding `shop.deps.get_clock` still works.
    """
    return CartService(
        store=request.app.state.cart_store,
        clock=clock,
        ids=ids,
        repository=repository,
    )


__all__ = ["CartService", "get_cart_service", "shipping_for", "discount_for", "Cart"]
