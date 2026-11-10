"""Racine pytest de l'atelier.

Deux responsabilites, et rien de plus :

1. l'option `--impl=a|b`, positionnee **avant** que l'application ne soit
   importee, pour que `shop.create_app()` construise la bonne implementation ;
2. l'horloge gelee optionnelle (`SHOP_FREEZE_AT`), utilisee par
   `scripts/check_dates.sh`.

Les fixtures `app` et `client` fournies ici sont volontairement
`function`-scoped : une application neuve par test. Tu peux t'en servir, ou
appeler `create_app()` toi-meme dans tes tests -- les deux sont corrects.
"""

from __future__ import annotations

import os
from typing import Iterator

import pytest

_FREEZER = None


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--impl",
        action="store",
        default=None,
        choices=("a", "b"),
        help="Implementation a piloter (defaut : la variable SHOP_IMPL, sinon 'a').",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Fixe SHOP_IMPL et l'horloge gelee avant tout import d'application."""
    impl = config.getoption("--impl")
    if impl:
        os.environ["SHOP_IMPL"] = impl

    frozen_at = os.environ.get("SHOP_FREEZE_AT")
    if frozen_at:
        from freezegun import freeze_time

        global _FREEZER
        _FREEZER = freeze_time(frozen_at)
        _FREEZER.start()


def pytest_unconfigure(config: pytest.Config) -> None:
    global _FREEZER
    if _FREEZER is not None:
        _FREEZER.stop()
        _FREEZER = None


def pytest_report_header(config: pytest.Config) -> list[str]:
    lines = ["implementation : SHOP_IMPL=" + os.environ.get("SHOP_IMPL", "a")]
    if os.environ.get("SHOP_FREEZE_AT"):
        lines.append("horloge gelee : " + os.environ["SHOP_FREEZE_AT"])
    if os.environ.get("SHOP_BUG") == "1":
        lines.append("BUG PLANTE : seuil de livraison gratuite abaisse a 500 centimes")
    return lines


@pytest.fixture
def app():
    """Une application neuve, pour ce test uniquement."""
    from shop import create_app

    return create_app()


@pytest.fixture
def client(app) -> Iterator:
    """Un TestClient sur une application neuve.

    `TestClient` n'est pas un double de test : c'est un transport en processus.
    Voir docs/TESTCLIENT.md.
    """
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
