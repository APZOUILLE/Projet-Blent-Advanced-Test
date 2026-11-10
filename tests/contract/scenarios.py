"""Les scenarios rejoues a l'identique sur A et sur B. FOURNI -- NE PAS MODIFIER."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

# Instants de reference, choisis par intention et non au hasard.
TUESDAY_10H = datetime(2026, 3, 10, 10, 0, tzinfo=PARIS)  # semaine, hors happy hour
TUESDAY_18H = datetime(2026, 3, 10, 18, 0, tzinfo=PARIS)  # debut de happy hour
TUESDAY_1959 = datetime(2026, 3, 10, 19, 59, tzinfo=PARIS)  # fin de happy hour
TUESDAY_20H = datetime(2026, 3, 10, 20, 0, tzinfo=PARIS)  # happy hour terminee
SATURDAY_1830 = datetime(2026, 3, 14, 18, 30, tzinfo=PARIS)  # samedi + happy hour
SUNDAY_11H = datetime(2026, 3, 15, 11, 0, tzinfo=PARIS)  # dimanche
DECEMBER_31 = datetime(2026, 12, 31, 23, 59, tzinfo=PARIS)  # dernier jour de NEWYEAR
JANUARY_1 = datetime(2026, 1, 1, 0, 5, tzinfo=PARIS)  # premier jour de l'annee


@dataclass(frozen=True)
class Item:
    sku: str
    quantity: int
    unit_price_cents: int


@dataclass(frozen=True)
class Scenario:
    """Un scenario metier rejouable a l'identique sur les deux implementations."""

    name: str
    items: tuple[Item, ...]
    instant: datetime = TUESDAY_10H
    coupon: str | None = None
    coupon_status: int = 204
    prior_order: bool = False
    removals: tuple[str, ...] = field(default=())


def _items(*triples: tuple[str, int, int]) -> tuple[Item, ...]:
    return tuple(Item(sku, quantity, price) for sku, quantity, price in triples)


SCENARIOS: tuple[Scenario, ...] = (
    # --- sous-total et seuil de livraison ---------------------------------
    Scenario("single-line-cheap", _items(("SKU-1", 1, 100))),
    Scenario("single-line-499", _items(("SKU-1", 1, 499))),
    Scenario("threshold-minus-one", _items(("SKU-1", 1, 4999))),
    Scenario("threshold-exact", _items(("SKU-1", 1, 5000))),
    Scenario("threshold-plus-one", _items(("SKU-1", 1, 5001))),
    Scenario("well-above-threshold", _items(("SKU-1", 3, 4000))),
    Scenario(
        "many-lines-unsorted",
        _items(("SKU-9", 2, 1500), ("SKU-1", 1, 999), ("SKU-5", 4, 250)),
    ),
    Scenario("cumulated-same-sku", _items(("SKU-1", 4, 300), ("SKU-1", 6, 300))),
    Scenario("max-quantity-per-sku", _items(("SKU-1", 10, 700))),
    Scenario(
        "removal-brings-below-threshold",
        _items(("SKU-1", 1, 4800), ("SKU-2", 1, 900)),
        removals=("SKU-2",),
    ),
    Scenario(
        "removal-of-absent-sku-is-a-noop",
        _items(("SKU-1", 2, 3000)),
        removals=("SKU-404",),
    ),
    Scenario("zero-priced-line", _items(("SKU-FREE", 3, 0), ("SKU-1", 1, 6000))),
    # --- WELCOME10 --------------------------------------------------------
    Scenario("welcome10-round-number", _items(("SKU-1", 1, 10000)), coupon="WELCOME10"),
    Scenario("welcome10-floor-99", _items(("SKU-1", 1, 999)), coupon="WELCOME10"),
    Scenario("welcome10-floor-half-cent", _items(("SKU-1", 1, 1005)), coupon="WELCOME10"),
    Scenario(
        "welcome10-discount-drops-below-threshold",
        _items(("SKU-1", 1, 5200)),
        coupon="WELCOME10",
    ),
    Scenario(
        "welcome10-discount-keeps-free-shipping",
        _items(("SKU-1", 1, 8000)),
        coupon="WELCOME10",
    ),
    Scenario(
        "welcome10-refused-for-returning-customer",
        _items(("SKU-1", 1, 10000)),
        coupon="WELCOME10",
        coupon_status=409,
        prior_order=True,
    ),
    # --- HAPPYHOUR --------------------------------------------------------
    Scenario(
        "happyhour-at-opening",
        _items(("SKU-1", 2, 2000)),
        instant=TUESDAY_18H,
        coupon="HAPPYHOUR",
    ),
    Scenario(
        "happyhour-last-minute",
        _items(("SKU-1", 1, 3333)),
        instant=TUESDAY_1959,
        coupon="HAPPYHOUR",
    ),
    Scenario(
        "happyhour-refused-before",
        _items(("SKU-1", 1, 3333)),
        instant=TUESDAY_10H,
        coupon="HAPPYHOUR",
        coupon_status=409,
    ),
    Scenario(
        "happyhour-refused-at-closing",
        _items(("SKU-1", 1, 3333)),
        instant=TUESDAY_20H,
        coupon="HAPPYHOUR",
        coupon_status=409,
    ),
    # --- WEEKEND ----------------------------------------------------------
    Scenario(
        "weekend-saturday",
        _items(("SKU-1", 1, 6000)),
        instant=SATURDAY_1830,
        coupon="WEEKEND",
    ),
    Scenario(
        "weekend-sunday-floor",
        _items(("SKU-1", 1, 1001)),
        instant=SUNDAY_11H,
        coupon="WEEKEND",
    ),
    Scenario(
        "weekend-refused-on-tuesday",
        _items(("SKU-1", 1, 6000)),
        instant=TUESDAY_10H,
        coupon="WEEKEND",
        coupon_status=409,
    ),
    # --- NEWYEAR ----------------------------------------------------------
    Scenario(
        "newyear-january",
        _items(("SKU-1", 1, 12345)),
        instant=JANUARY_1,
        coupon="NEWYEAR",
    ),
    Scenario(
        "newyear-last-day",
        _items(("SKU-1", 3, 777)),
        instant=DECEMBER_31,
        coupon="NEWYEAR",
    ),
    Scenario(
        "newyear-drops-below-threshold",
        _items(("SKU-1", 1, 6200)),
        instant=DECEMBER_31,
        coupon="NEWYEAR",
    ),
    # --- coupons inconnus et remplacement ---------------------------------
    Scenario(
        "unknown-coupon-leaves-cart-untouched",
        _items(("SKU-1", 1, 2500)),
        coupon="NOPE",
        coupon_status=404,
    ),
    Scenario(
        "lowercase-coupon-is-unknown",
        _items(("SKU-1", 1, 2500)),
        coupon="welcome10",
        coupon_status=404,
    ),
    Scenario(
        "weekend-on-saturday-with-many-lines",
        _items(("SKU-3", 2, 1234), ("SKU-1", 1, 4321), ("SKU-2", 5, 99)),
        instant=SATURDAY_1830,
        coupon="WEEKEND",
    ),
    Scenario(
        "happyhour-on-saturday-evening",
        _items(("SKU-1", 1, 5100)),
        instant=SATURDAY_1830,
        coupon="HAPPYHOUR",
    ),
)
