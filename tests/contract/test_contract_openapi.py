"""Les deux implementations exposent la meme surface HTTP. FOURNI -- NE PAS MODIFIER.

On normalise avant de comparer : routes, methodes et codes de statut declares.
On ignore volontairement les schemas de corps (A renvoie des dicts, B des
modeles Pydantic : deux facons legitimes de tenir le meme contrat) et l'ordre
des cles.
"""

from __future__ import annotations

from shop import build_app

CONTRACT_ROUTES = {
    ("/carts", "post"),
    ("/carts/{cart_id}", "get"),
    ("/carts/{cart_id}/items", "post"),
    ("/carts/{cart_id}/items/{sku}", "delete"),
    ("/carts/{cart_id}/coupon", "put"),
    ("/carts/{cart_id}/checkout", "post"),
    ("/orders/{order_id}", "get"),
    ("/customers/{customer_id}/orders", "get"),
}


def _normalised_surface(impl: str) -> dict[tuple[str, str], list[str]]:
    """(route, methode) -> codes de statut declares, tries."""
    schema = build_app(impl).openapi()
    surface: dict[tuple[str, str], list[str]] = {}
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            surface[(path, method)] = sorted(operation["responses"])
    return surface


def test_both_implementations_declare_the_same_routes_and_status_codes() -> None:
    assert _normalised_surface("a") == _normalised_surface("b")


def test_the_declared_surface_is_exactly_the_documented_contract() -> None:
    """Une route de debug ne doit jamais apparaitre dans le schema public."""
    for impl in ("a", "b"):
        assert set(_normalised_surface(impl)) == CONTRACT_ROUTES, impl


def test_business_error_codes_are_documented_where_the_contract_says_so() -> None:
    for impl in ("a", "b"):
        surface = _normalised_surface(impl)
        assert "404" in surface[("/carts/{cart_id}", "get")], impl
        assert "409" in surface[("/carts/{cart_id}/coupon", "put")], impl
        assert "503" in surface[("/carts/{cart_id}/checkout", "post")], impl


def test_openapi_is_served_so_that_docs_works() -> None:
    for impl in ("a", "b"):
        schema = build_app(impl).openapi()
        assert schema["openapi"].startswith("3.")
        assert schema["info"]["version"] == "1.0.0"
