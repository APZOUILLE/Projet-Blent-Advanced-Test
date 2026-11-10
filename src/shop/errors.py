"""Business errors and the HTTP mapping shared by every implementation.

The mapping lives here, once, so that implementation A and implementation B
answer with the exact same status code and the exact same machine-readable
`code` -- while remaining free to word their `message` differently.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class BusinessError(Exception):
    """Base class for every expected, documented business failure.

    Subclasses carry the HTTP status code and the stable `code` string that
    clients are allowed to depend on.

    A subclass may also enrich its response: `extra_fields()` adds keys inside
    the `error` object, and `response_headers()` adds HTTP headers. Both are
    part of the contract for the codes that use them -- see
    `docs/CONTRAT_HTTP.md`.
    """

    status_code: int = 400
    code: str = "BUSINESS_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def extra_fields(self) -> dict[str, str]:
        """Extra keys to merge into the `error` object of the response."""
        return {}

    def response_headers(self) -> dict[str, str]:
        """Extra HTTP headers to attach to the error response."""
        return {}


class CartNotFound(BusinessError):
    status_code = 404
    code = "CART_NOT_FOUND"


class OrderNotFound(BusinessError):
    status_code = 404
    code = "ORDER_NOT_FOUND"


class UnknownCoupon(BusinessError):
    status_code = 404
    code = "UNKNOWN_COUPON"


class CartAlreadyExists(BusinessError):
    """The customer already has an active cart.

    The response carries the id of that cart -- in the body and in the
    `Location` header -- so that a client is never locked out of its own cart.
    """

    status_code = 409
    code = "CART_ALREADY_EXISTS"

    def __init__(self, message: str, cart_id: str) -> None:
        super().__init__(message)
        self.cart_id = cart_id

    def extra_fields(self) -> dict[str, str]:
        return {"cart_id": self.cart_id}

    def response_headers(self) -> dict[str, str]:
        return {"Location": "/carts/" + self.cart_id}


class EmptyCart(BusinessError):
    status_code = 409
    code = "EMPTY_CART"


class QuantityLimitExceeded(BusinessError):
    status_code = 409
    code = "QUANTITY_LIMIT_EXCEEDED"


class CouponNotApplicable(BusinessError):
    status_code = 409
    code = "COUPON_NOT_APPLICABLE"


class PersistenceUnavailable(BusinessError):
    """Storage could not be reached. No order has been created."""

    status_code = 503
    code = "PERSISTENCE_UNAVAILABLE"


def error_payload(exc: BusinessError) -> dict[str, dict[str, str]]:
    """Return the documented error body for a business error."""
    error: dict[str, str] = {"code": exc.code, "message": exc.message}
    error.update(exc.extra_fields())
    return {"error": error}


def install_error_handlers(app: FastAPI) -> None:
    """Wire the shared business-error to HTTP translation onto an app."""

    def handle(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, BusinessError)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc),
            headers=exc.response_headers(),
        )

    app.add_exception_handler(BusinessError, handle)
