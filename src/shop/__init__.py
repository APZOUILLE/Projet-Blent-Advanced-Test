"""Public entry points of the shop application.

There is deliberately **no module-level `app` object** in this package. The only
way to get an application is to call `create_app()`, which builds a brand new
one -- fresh carts, fresh database, fresh providers.

That is not a stylistic choice: a module-level `app` is shared state, and shared
state is what makes a test suite depend on its own execution order. Module 3 of
the workshop is entirely about this.

Which implementation you get is decided by the `SHOP_IMPL` environment variable
(`a` by default). The two implementations answer the exact same HTTP contract,
documented in `docs/CONTRAT_HTTP.md`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import FastAPI

    from shop.ports import OrderRepository

__all__ = [
    "create_app",
    "create_order_repository",
    "selected_impl",
    "build_app",
    "build_order_repository",
]

_IMPLEMENTATIONS = ("a", "b")


def selected_impl() -> str:
    """Return the implementation selected by the `SHOP_IMPL` env var."""
    impl = os.environ.get("SHOP_IMPL", "a").strip().lower()
    if impl not in _IMPLEMENTATIONS:
        raise RuntimeError(
            f"SHOP_IMPL={impl!r} est inconnu. Valeurs possibles : "
            f"{' ou '.join(_IMPLEMENTATIONS)}."
        )
    return impl


def create_app() -> "FastAPI":
    """Build a brand new application for the selected implementation.

    Call this once per test. It is cheap: the default repository runs on an
    in-memory SQLite database.
    """
    return build_app(selected_impl())


def create_order_repository(database: str = ":memory:") -> "OrderRepository":
    """Build the real SQLite order repository of the selected implementation.

    Args:
        database: `":memory:"` (default) or a path to a SQLite file.

    Use this in tests instead of importing `shop.impl_a...` or `shop.impl_b...`:
    the schemas differ between implementations, the port does not.
    """
    return build_order_repository(selected_impl(), database)


def build_app(impl: str) -> "FastAPI":
    """Build the application of an explicitly named implementation.

    Reserved for `tests/contract/`, which needs both applications alive in the
    same process to prove they are interchangeable. Exercise and solution tests
    must use `create_app()` so that the swap can actually detect coupling.
    """
    if impl == "a":
        from shop.impl_a.main import create_app_a

        return create_app_a()
    if impl == "b":
        from shop.impl_b.app import create_app_b

        return create_app_b()
    raise RuntimeError(f"Implémentation inconnue : {impl!r}")


def build_order_repository(impl: str, database: str = ":memory:") -> "OrderRepository":
    """Build the SQLite repository of an explicitly named implementation."""
    if impl == "a":
        from shop.impl_a.repository import SqliteOrderRepository as RepositoryA

        return RepositoryA(database)
    if impl == "b":
        from shop.impl_b.repository import SqliteOrderRepository as RepositoryB

        return RepositoryB(database)
    raise RuntimeError(f"Implémentation inconnue : {impl!r}")
