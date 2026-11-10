"""SHARED dependency providers. Do not duplicate these per implementation.

Why this module is the single most important file of the repo
------------------------------------------------------------
The keys of `app.dependency_overrides` are **the provider callables
themselves**, compared by identity:

    app.dependency_overrides[get_clock] = lambda: FixedClock(...)

If implementation A and implementation B each defined their own `get_clock`,
then an override written against A's `get_clock` would silently stop applying
once B is running -- no error, no warning, just a test that quietly exercises
the real clock again.

So both implementations import *these* callables and use them in their route
signatures via `Depends`. That is what makes a single test suite able to drive
either implementation.

The default value returned by each provider is stored on `app.state` by
`create_app()`, which keeps the default *per app instance* -- one fresh clock,
id generator and repository per `create_app()` call.
"""

from __future__ import annotations

from fastapi import Request

from shop.ports import Clock, IdGenerator, OrderRepository


def get_clock(request: Request) -> Clock:
    """Provide the application clock.

    Override this in a test when the scenario needs an instant you cannot wait
    for (happy hour, a Saturday, a year boundary).
    """
    return request.app.state.clock


def get_id_generator(request: Request) -> IdGenerator:
    """Provide the order id generator.

    You almost never need to override this: order ids are opaque, so a test
    should carry the id it received instead of predicting it.
    """
    return request.app.state.id_generator


def get_order_repository(request: Request) -> OrderRepository:
    """Provide the order repository.

    The real repository runs on SQLite and accepts `":memory:"`, so most tests
    can use it as is. Override it to observe an interaction (a spy) or to reach
    a state the real one cannot produce on demand (storage down, a customer
    with 300 orders).
    """
    return request.app.state.order_repository
