"""Module 3 -- la suite qui passe... quand on ne la derange pas.

Chaque test passe seul. La suite passe dans l'ordre du fichier, un mardi
apres-midi. Elle casse des qu'on change l'ordre (`make shuffle`) ou la date
(`make check-dates`).

Deux familles de bugs, melangees exactement comme dans la vraie vie :

* de l'etat partage entre tests (application, base, surcharges, espion, panier) ;
* des attentes qui dependent de l'heure ou de la date reelles.

Ta mission : rendre cette suite deterministe sans perdre une seule intention
metier.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from shop import create_app, create_order_repository, deps
from shop.ports import OrderRecord

PARIS = ZoneInfo("Europe/Paris")

# --- etat partage par tout le module ---------------------------------------

# Une seule application pour tous les tests du fichier.
app = create_app()

# Une seule base pour tous les tests, dans un fichier temporaire.
# (Le PID dans le nom evite qu'un autre lancement de pytest tienne le fichier
# ouvert : le bug qu'on veut montrer est le partage ENTRE TESTS, pas entre
# processus.)
TEMP_DIR = Path(tempfile.gettempdir())
for _stale in TEMP_DIR.glob("atelier_tests_orders_*.sqlite"):
    with suppress(OSError):  # un fichier encore ouvert ailleurs resiste
        _stale.unlink()
SHARED_DB = TEMP_DIR / f"atelier_tests_orders_{os.getpid()}.sqlite"
SHARED_REPOSITORY = create_order_repository(str(SHARED_DB))
app.dependency_overrides[deps.get_order_repository] = lambda: SHARED_REPOSITORY

# Un identifiant client en dur, utilise par plusieurs tests.
CUSTOMER = "flaky-customer"

# Le panier "prepare" par un test pour le suivant.
PREPARED_CART: str = ""

SATURDAY_1830 = datetime(2026, 3, 14, 18, 30, tzinfo=PARIS)
NEW_YEAR_INSTANT = datetime(2025, 1, 15, 10, 0, tzinfo=PARIS)


@dataclass
class SpyOrderRepository:
    """Espion par delegation : observe `save`, delegue tout le reste."""

    inner: object
    saved: list[OrderRecord] = field(default_factory=list)

    def save(self, order: OrderRecord) -> None:
        self.saved.append(order)
        self.inner.save(order)

    def get(self, order_id: str):
        return self.inner.get(order_id)

    def list_for_customer(self, customer_id: str):
        return self.inner.list_for_customer(customer_id)

    def count_for_customer(self, customer_id: str) -> int:
        return self.inner.count_for_customer(customer_id)


# Un seul espion pour tout le module.
SPY = SpyOrderRepository(SHARED_REPOSITORY)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Un client unique pour toute la session de tests."""
    return TestClient(app)


def _cart_with(client: TestClient, *items: tuple[str, int, int]) -> str:
    created = client.post("/carts", json={"customer_id": CUSTOMER})
    if created.status_code == 409:
        # le client a deja un panier en cours : on le reprend
        cart_id = created.json()["error"]["cart_id"]
    else:
        cart_id = created.json()["cart_id"]
    for sku, quantity, price in items:
        client.post(
            f"/carts/{cart_id}/items",
            json={"sku": sku, "quantity": quantity, "unit_price_cents": price},
        )
    return cart_id


# ---------------------------------------------------------------------------
# Etat partage et ordre d'execution
# ---------------------------------------------------------------------------


def test_the_customer_has_no_order_yet(client: TestClient) -> None:
    listing = client.get(f"/customers/{CUSTOMER}/orders").json()

    assert listing["count"] == 0


def test_welcome10_applies_to_a_first_time_customer(client: TestClient) -> None:
    cart_id = _cart_with(client, ("SKU-1", 1, 10000))

    response = client.put(f"/carts/{cart_id}/coupon", json={"code": "WELCOME10"})

    assert response.status_code == 204
    assert client.get(f"/carts/{cart_id}").json()["discount_cents"] == 1000


def test_a_checkout_shows_up_in_the_customer_orders(client: TestClient) -> None:
    cart_id = _cart_with(client, ("SKU-1", 2, 1500))

    assert client.post(f"/carts/{cart_id}/checkout").status_code == 201

    assert client.get(f"/customers/{CUSTOMER}/orders").json()["count"] == 1


def test_a_second_checkout_is_counted_too(client: TestClient) -> None:
    cart_id = _cart_with(client, ("SKU-2", 1, 4000))

    assert client.post(f"/carts/{cart_id}/checkout").status_code == 201

    assert client.get(f"/customers/{CUSTOMER}/orders").json()["count"] == 2


def test_a_successful_checkout_is_persisted_once(client: TestClient) -> None:
    app.dependency_overrides[deps.get_order_repository] = lambda: SPY
    cart_id = _cart_with(client, ("SKU-3", 1, 2500))

    order = client.post(f"/carts/{cart_id}/checkout").json()

    assert len(SPY.saved) == 1
    assert SPY.saved[0].order_id == order["order_id"]


def test_the_spy_still_lets_the_order_be_read_back(client: TestClient) -> None:
    cart_id = _cart_with(client, ("SKU-4", 1, 2500))

    order = client.post(f"/carts/{cart_id}/checkout").json()

    assert len(SPY.saved) == 2
    assert client.get(f"/orders/{order['order_id']}").status_code == 200
    app.dependency_overrides[deps.get_order_repository] = lambda: SHARED_REPOSITORY


# ---------------------------------------------------------------------------
# Fragilite temporelle
# ---------------------------------------------------------------------------


@pytest.mark.temporal
def test_happyhour_is_refused_outside_the_evening(client: TestClient) -> None:
    cart_id = _cart_with(client, ("SKU-1", 1, 4000))

    response = client.put(f"/carts/{cart_id}/coupon", json={"code": "HAPPYHOUR"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "COUPON_NOT_APPLICABLE"


@pytest.mark.temporal
def test_weekend_is_refused_on_a_weekday(client: TestClient) -> None:
    cart_id = _cart_with(client, ("SKU-1", 1, 4000))

    response = client.put(f"/carts/{cart_id}/coupon", json={"code": "WEEKEND"})

    assert response.status_code == 409


@pytest.mark.temporal
def test_an_order_is_placed_today(client: TestClient) -> None:
    cart_id = _cart_with(client, ("SKU-1", 1, 2500))

    order = client.post(f"/carts/{cart_id}/checkout").json()

    placed_at = datetime.fromisoformat(order["placed_at"]).astimezone(PARIS)
    assert placed_at.date() == date.today()


@pytest.mark.temporal
def test_newyear_is_still_running_this_year(client: TestClient) -> None:
    app.dependency_overrides[deps.get_clock] = lambda: FixedClock(NEW_YEAR_INSTANT)
    try:
        cart_id = _cart_with(client, ("SKU-1", 1, 10000))
        assert client.put(f"/carts/{cart_id}/coupon", json={"code": "NEWYEAR"}).status_code == 204
        order = client.post(f"/carts/{cart_id}/checkout").json()

        assert order["discount_cents"] == 2000
        # La promo court jusqu'au 31 decembre : il doit rester des jours.
        assert datetime.fromisoformat(order["placed_at"]).year == date.today().year
        end_of_promo = date(date.today().year, 12, 31)
        assert (end_of_promo - date.today()) >= timedelta(days=1)
    finally:
        app.dependency_overrides.pop(deps.get_clock, None)


@pytest.mark.temporal
def test_the_order_is_dated_from_today(client: TestClient) -> None:
    cart_id = _cart_with(client, ("SKU-1", 1, 2500))

    order = client.post(f"/carts/{cart_id}/checkout").json()

    expected_prefix = datetime.now(PARIS).strftime("%Y-%m-%d")
    assert order["placed_at"].startswith(expected_prefix)


# ---------------------------------------------------------------------------
# Surcharge oubliee, et le panier prepare pour le voisin
# ---------------------------------------------------------------------------


def test_shipping_is_free_above_the_threshold(client: TestClient) -> None:
    # copie-colle d'un autre test : on fige l'horloge par habitude
    app.dependency_overrides[deps.get_clock] = lambda: FixedClock(SATURDAY_1830)

    cart_id = _cart_with(client, ("SKU-1", 1, 5001))

    cart = client.get(f"/carts/{cart_id}").json()
    assert cart["shipping_cents"] == 0
    assert cart["total_cents"] == 5001


def test_the_weekend_coupon_is_accepted(client: TestClient) -> None:
    global PREPARED_CART
    cart_id = _cart_with(client, ("SKU-1", 1, 10000))

    assert client.put(f"/carts/{cart_id}/coupon", json={"code": "WEEKEND"}).status_code == 204

    PREPARED_CART = cart_id  # le test suivant reutilise ce panier


def test_the_weekend_discount_is_fifteen_percent(client: TestClient) -> None:
    order = client.post(f"/carts/{PREPARED_CART}/checkout").json()

    assert order["subtotal_cents"] == 20000
    assert order["discount_cents"] == 3000
    assert order["total_cents"] == 17000
