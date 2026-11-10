"""Application factory of implementation B.

Layered on purpose: `routers/` -> `services/` -> `domain/`. No business rule
lives in this file, and none lives in a handler.
"""

from __future__ import annotations

import base64
import secrets
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from shop import errors
from shop.impl_b.domain.cart import InMemoryCartStore
from shop.impl_b.repository import SqliteOrderRepository
from shop.impl_b.routers import carts, orders


class UtcClock:
    """The real clock. Returns an aware UTC datetime."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class Base32IdGenerator:
    """`ORD-` + 12 uppercase base32 characters."""

    def new_order_id(self) -> str:
        raw = base64.b32encode(secrets.token_bytes(8)).decode("ascii")
        return "ORD-" + raw[:12]


def create_app_b() -> FastAPI:
    """Build a fresh implementation-B application."""
    app = FastAPI(title="Shop (implementation B)", version="1.0.0")

    app.state.cart_store = InMemoryCartStore()
    app.state.clock = UtcClock()
    app.state.id_generator = Base32IdGenerator()
    app.state.order_repository = SqliteOrderRepository(":memory:")

    errors.install_error_handlers(app)

    def handle_invalid_body(request: Request, exc: Exception) -> JSONResponse:
        """Answer 422 with this implementation's own shape.

        The contract guarantees the *status code* of a body validation failure,
        never the shape of its payload -- and the two implementations of this
        repo deliberately disagree on that shape. A test that reads
        `response.json()["detail"]` has bet on FastAPI's internals.
        """
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_BODY",
                    "message": "The submitted payload does not match the schema",
                }
            },
        )

    app.add_exception_handler(RequestValidationError, handle_invalid_body)

    app.include_router(carts.router)
    app.include_router(orders.router)
    return app
