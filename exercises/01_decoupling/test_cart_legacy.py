"""Module 1 -- la suite heritee. Dix tests verts sur A, dix tests morts sur B.

Chacun de ces tests protege une intention metier reelle. Chacun est ecrit d'une
facon qui l'attache a l'implementation A. Ta mission : garder l'intention,
jeter l'attache.

Lance `make test` (vert), puis `make swap M=1` (rouge). Le rouge n'est pas une
regression : c'est le detecteur qui fait son travail.

Chaque test porte en commentaire le vice qu'il incarne. Huit sont a reparer.
Deux ne protegent aucune regle metier -- a toi de trouver lesquels, et de les
supprimer en justifiant.
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient

from shop import create_app, create_order_repository, deps

# Import direct de l'implementation A : premiere odeur, avant meme le premier test.
from shop.impl_a.main import AddItemBody, compute_cart_pricing

CUSTOMER = "legacy-customer"


def _new_client() -> tuple[object, TestClient]:
    app = create_app()
    return app, TestClient(app)


def _cart_with(client: TestClient, *items: tuple[str, int, int]) -> str:
    cart_id = client.post("/carts", json={"customer_id": CUSTOMER}).json()["cart_id"]
    for sku, quantity, price in items:
        client.post(
            f"/carts/{cart_id}/items",
            json={"sku": sku, "quantity": quantity, "unit_price_cents": price},
        )
    return cart_id


def _endpoint(app, method: str, path: str):
    """Retrouve la fonction de handler derriere une route."""
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(
            route, "methods", ()
        ):
            return route.endpoint
    raise AssertionError(f"route introuvable : {method} {path}")


# ---------------------------------------------------------------------------
# 1. Vice : la logique metier est testee en direct, l'etat est lu dans les
# entrailles de l'application. Aucune route n'est appelee pour verifier.
# ---------------------------------------------------------------------------


def test_cart_total_adds_shipping_below_the_free_threshold() -> None:
    app, client = _new_client()
    cart_id = _cart_with(client, ("SKU-1", 2, 1500))

    cart = app.state.carts[cart_id]
    pricing = compute_cart_pricing(cart, coupon=None)

    assert pricing["subtotal_cents"] == 3000
    assert pricing["shipping_cents"] == 590
    assert pricing["total_cents"] == 3590


# ---------------------------------------------------------------------------
# 2. Vice : le handler est appele comme une simple fonction Python, avec des
# arguments fabriques a la main. Le test depend de sa signature.
# ---------------------------------------------------------------------------


def test_adding_an_item_answers_204() -> None:
    app, client = _new_client()
    cart_id = _cart_with(client)

    handler = _endpoint(app, "POST", "/carts/{cart_id}/items")
    response = handler(
        request=SimpleNamespace(app=app),
        cart_id=cart_id,
        body=AddItemBody(sku="SKU-1", quantity=2, unit_price_cents=1500),
    )

    assert response.status_code == 204


# ---------------------------------------------------------------------------
# 3. Vice : monkeypatch (voir vocabulaire) d'une constante interne pour changer
# le comportement de l'application. Le test depend de l'implementation.
# Recentre le test sur l'intention : le code de reduction WELCOME10, pas besoin
# de savoir qu'il est configure dans une constante.
# ---------------------------------------------------------------------------


def test_welcome10_applies_the_configured_percentage(monkeypatch) -> None:
    monkeypatch.setattr("shop.impl_a.main.PRICING_TABLE", {"WELCOME10": 50})

    _, client = _new_client()
    cart_id = _cart_with(client, ("SKU-1", 1, 10000))
    assert (
        client.put(f"/carts/{cart_id}/coupon", json={"code": "WELCOME10"}).status_code
        == 204
    )

    assert client.get(f"/carts/{cart_id}").json()["discount_cents"] == 5000


# ---------------------------------------------------------------------------
# 4. Vice : egalite stricte sur tout le corps de la reponse, champs de debug
# compris. Le test devient un moulage de l'implementation.
# ---------------------------------------------------------------------------


def test_cart_view_returns_the_expected_body() -> None:
    _, client = _new_client()
    cart_id = _cart_with(client, ("SKU-1", 2, 1500))

    assert client.get(f"/carts/{cart_id}").json() == {
        "cart_id": cart_id,
        "customer_id": CUSTOMER,
        "lines": [{"sku": "SKU-1", "quantity": 2, "unit_price_cents": 1500}],
        "coupon": None,
        "subtotal_cents": 3000,
        "discount_cents": 0,
        "shipping_cents": 590,
        "total_cents": 3590,
        "_debug_impl": "a",
        "raw_total": 3000,
    }


# ---------------------------------------------------------------------------
# 5. Vice : dependance a l'ordre des lignes, que le contrat ne garantit pas.
# ---------------------------------------------------------------------------


def test_lines_keep_their_prices() -> None:
    _, client = _new_client()
    cart_id = _cart_with(client, ("SKU-9", 1, 2500), ("SKU-1", 3, 400))

    lines = client.get(f"/carts/{cart_id}").json()["lines"]

    assert lines[0]["sku"] == "SKU-9"
    assert lines[0]["unit_price_cents"] == 2500
    assert lines[1]["sku"] == "SKU-1"
    assert lines[1]["quantity"] == 3


# ---------------------------------------------------------------------------
# 6. Vice : assertion sur le format d'un identifiant que le contrat declare
# opaque.
# ---------------------------------------------------------------------------


def test_checkout_returns_a_well_formed_order_id() -> None:
    _, client = _new_client()
    cart_id = _cart_with(client, ("SKU-1", 1, 2500))

    order_id = client.post(f"/carts/{cart_id}/checkout").json()["order_id"]

    assert len(order_id) == 12
    assert order_id.startswith("ORD-")
    assert order_id[4:].islower()


# ---------------------------------------------------------------------------
# 7. Vice : assertion sur la prose d'un message d'erreur.
# ---------------------------------------------------------------------------


def test_checking_out_an_empty_cart_is_refused() -> None:
    _, client = _new_client()
    cart_id = _cart_with(client)

    response = client.post(f"/carts/{cart_id}/checkout")

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Cart is empty"


# ---------------------------------------------------------------------------
# 8. Vice : assertion sur la charge utile interne d'une erreur de validation.
# ---------------------------------------------------------------------------


def test_a_negative_quantity_is_rejected() -> None:
    _, client = _new_client()
    cart_id = _cart_with(client)

    response = client.post(
        f"/carts/{cart_id}/items",
        json={"sku": "SKU-1", "quantity": -2, "unit_price_cents": 1500},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "quantity"]


# ---------------------------------------------------------------------------
# 9. Vice : lecture directe en base, avec le schema de l'implementation A.
# ---------------------------------------------------------------------------


def test_checkout_persists_the_total(tmp_path) -> None:
    database = str(tmp_path / "orders.sqlite")
    repository = create_order_repository(database)

    app = create_app()
    app.dependency_overrides[deps.get_order_repository] = lambda: repository
    client = TestClient(app)

    cart_id = _cart_with(client, ("SKU-1", 2, 1500))
    order_id = client.post(f"/carts/{cart_id}/checkout").json()["order_id"]

    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT total FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    connection.close()

    assert row[0] == 3590


# ---------------------------------------------------------------------------
# 10. Vice : verification de l'etat par une route de debug hors contrat.
# ---------------------------------------------------------------------------


def test_the_cart_holds_what_was_added() -> None:
    _, client = _new_client()
    cart_id = _cart_with(client, ("SKU-1", 2, 1500))

    state = client.get("/_internal/state").json()

    assert state["carts"][cart_id]["items"]["SKU-1"]["quantity"] == 2
