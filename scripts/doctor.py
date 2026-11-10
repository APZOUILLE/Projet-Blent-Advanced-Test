"""Verifie que l'atelier est jouable sur cette machine, avant de commencer.

    poetry run python scripts/doctor.py

Aucun acces reseau, aucun serveur a lancer : tout se passe en processus.
"""

from __future__ import annotations

import importlib
import os
import platform
import sys
from pathlib import Path

WIDTH = 74
OK = "  [ OK ]  "
KO = "  [ KO ]  "

problems: list[str] = []


def check(label: str, ok: bool, remedy: str = "") -> bool:
    print((OK if ok else KO) + label)
    if not ok and remedy:
        problems.append(remedy)
    return ok


def main() -> int:
    print()
    print("=" * WIDTH)
    print("  DOCTOR -- l'atelier est-il jouable sur cette machine ?")
    print("=" * WIDTH)
    print()

    version = sys.version_info
    check(
        f"Python {platform.python_version()} (3.12 ou plus recent attendu)",
        version >= (3, 12),
        "Installe Python 3.12+, puis relance `poetry env use 3.12 && poetry install`.",
    )

    for module, why in (
        ("fastapi", "dependance runtime"),
        ("pytest", "lanceur de tests"),
        ("pytest_cov", "mesure la couverture (make coverage)"),
        ("pytest_randomly", "melange l'ordre d'execution (make shuffle)"),
        ("freezegun", "gele l'horloge (make check-dates)"),
        ("httpx", "requis par TestClient"),
        ("uvicorn", "serveur pour explorer /docs a la main"),
        ("sqlite3", "stdlib, persistance des commandes"),
    ):
        try:
            importlib.import_module(module)
            check(f"import {module:<16} ({why})", True)
        except ImportError:
            check(
                f"import {module:<16} ({why})",
                False,
                f"`{module}` manque : lance `poetry install`.",
            )

    try:
        from zoneinfo import ZoneInfo

        ZoneInfo("Europe/Paris")
        check("fuseau Europe/Paris disponible", True)
    except Exception:
        check(
            "fuseau Europe/Paris disponible",
            False,
            "Sur Windows, la base de fuseaux vient du paquet `tzdata` : "
            "`poetry install` doit l'installer.",
        )

    root = Path(__file__).resolve().parent.parent
    for path in (
        "src/shop/deps.py",
        "docs/CONTRAT_HTTP.md",
        "tests/contract",
        "exercises/01_decoupling/test_cart_legacy.py",
    ):
        check(f"present : {path}", (root / path).exists(), f"{path} est introuvable.")

    # Sans le bit executable, `make swap` repond "Permission denied" alors que
    # tout le reste est vert. Un diagnostic qui ne verifie pas ca donne un feu
    # vert mensonger -- exactement ce qu'un atelier sur les faux positifs ne
    # doit pas faire.
    not_executable = sorted(
        script.name
        for script in list((root / "scripts").glob("*.sh")) + [root / "make.sh"]
        if script.exists() and not os.access(script, os.X_OK)
    )
    check(
        "les scripts shell sont executables",
        not not_executable,
        "Manque le bit executable sur : "
        + ", ".join(not_executable)
        + ". Corrige avec : chmod +x scripts/*.sh make.sh"
        + " && git update-index --chmod=+x scripts/*.sh make.sh",
    )

    sys.path.insert(0, str(root / "src"))
    apps_ok = True
    try:
        from shop import build_app, build_order_repository, deps

        for impl in ("a", "b"):
            app = build_app(impl)
            build_order_repository(impl, ":memory:")
            routes = {getattr(route, "path", "") for route in app.routes}
            assert "/carts/{cart_id}/checkout" in routes
        check("les deux implementations se construisent", True)
    except Exception as exc:  # pragma: no cover - diagnostic
        apps_ok = False
        check(
            "les deux implementations se construisent",
            False,
            f"Echec de construction : {exc!r}",
        )

    if apps_ok:
        try:
            from datetime import datetime, timezone

            from fastapi.testclient import TestClient

            class FixedClock:
                def now(self):
                    return datetime(2026, 3, 14, 18, 30, tzinfo=timezone.utc)

            for impl in ("a", "b"):
                app = build_app(impl)
                app.dependency_overrides[deps.get_clock] = FixedClock
                client = TestClient(app)
                cart_id = client.post("/carts", json={"customer_id": "doctor"}).json()[
                    "cart_id"
                ]
                client.post(
                    f"/carts/{cart_id}/items",
                    json={"sku": "SKU-1", "quantity": 1, "unit_price_cents": 2500},
                )
                order = client.post(f"/carts/{cart_id}/checkout").json()
                assert order["placed_at"].startswith("2026-03-14"), order["placed_at"]
            check("une surcharge de get_clock agit sur A et sur B", True)
        except Exception as exc:  # pragma: no cover - diagnostic
            check(
                "une surcharge de get_clock agit sur A et sur B",
                False,
                f"Le test de sanite des providers echoue : {exc!r}",
            )

    print()
    if problems:
        print("  " + "-" * (WIDTH - 4))
        print("  A CORRIGER AVANT DE COMMENCER")
        print("  " + "-" * (WIDTH - 4))
        for problem in problems:
            print("    * " + problem)
        print()
        return 1

    print("  Tout est en place. Ouvre README.md et commence par le module 0.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
