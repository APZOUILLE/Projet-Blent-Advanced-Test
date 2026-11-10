"""Pydantic request and response models of implementation B.

Implementation A returns raw dictionaries with extra debug keys. Here the views
are typed models with exactly the guaranteed fields and nothing more. Both are
valid answers to the same contract -- which is precisely why a test must not
assert on a whole response body with `==`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateCartPayload(BaseModel):
    customer_id: str = Field(min_length=1)


class AddItemPayload(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price_cents: int = Field(ge=0)


class CouponPayload(BaseModel):
    code: str = Field(min_length=1)


class CartCreated(BaseModel):
    cart_id: str


class LineView(BaseModel):
    sku: str
    quantity: int
    unit_price_cents: int


class CartView(BaseModel):
    cart_id: str
    customer_id: str
    lines: list[LineView]
    coupon: str | None
    subtotal_cents: int
    discount_cents: int
    shipping_cents: int
    total_cents: int


class OrderView(BaseModel):
    order_id: str
    customer_id: str
    lines: list[LineView]
    subtotal_cents: int
    discount_cents: int
    shipping_cents: int
    total_cents: int
    placed_at: str


class CustomerOrdersView(BaseModel):
    count: int
    orders: list[OrderView]
