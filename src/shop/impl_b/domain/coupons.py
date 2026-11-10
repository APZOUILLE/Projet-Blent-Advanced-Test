"""Coupon strategies of implementation B, kept in a registry.

Implementation A does the same job with an `if/elif` chain. Same percentages,
same conditions, same rounding -- `tests/contract/` proves it to the cent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


@dataclass(frozen=True)
class CouponContext:
    """Everything a coupon needs to decide whether it applies."""

    customer_id: str
    local_now: datetime
    orders_already_placed: int


@dataclass(frozen=True)
class Coupon:
    code: str
    percent: int
    applies: Callable[[CouponContext], bool]
    refusal: str


def _first_order_only(context: CouponContext) -> bool:
    return context.orders_already_placed == 0


def _during_happy_hour(context: CouponContext) -> bool:
    return 18 <= context.local_now.hour < 20


def _during_weekend(context: CouponContext) -> bool:
    return context.local_now.weekday() in (5, 6)


def _before_end_of_year(context: CouponContext) -> bool:
    today = context.local_now.date()
    return today <= today.replace(month=12, day=31)


COUPON_REGISTRY: dict[str, Coupon] = {
    coupon.code: coupon
    for coupon in (
        Coupon(
            code="WELCOME10",
            percent=10,
            applies=_first_order_only,
            refusal="This customer has already ordered, WELCOME10 no longer applies",
        ),
        Coupon(
            code="HAPPYHOUR",
            percent=5,
            applies=_during_happy_hour,
            refusal="HAPPYHOUR is only redeemable between 6pm and 8pm, Paris time",
        ),
        Coupon(
            code="WEEKEND",
            percent=15,
            applies=_during_weekend,
            refusal="WEEKEND is only redeemable on saturdays and sundays",
        ),
        Coupon(
            code="NEWYEAR",
            percent=20,
            applies=_before_end_of_year,
            refusal="NEWYEAR ran out on december 31st",
        ),
    )
}
