from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


def violated_constraint(exc: IntegrityError) -> str | None:
    """Name of the constraint or unique index PostgreSQL reported, if any."""
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def is_foreign_key_violation(exc: IntegrityError) -> bool:
    """foreign_key_violation (NO ACTION keys) or restrict_violation (RESTRICT keys)."""
    return getattr(exc.orig, "sqlstate", None) in {"23503", "23001"}


class DomainError(Exception):
    """Business-rule failure raised by services and rendered as `{"detail": ...}`."""

    status_code = 400
    default_detail = "Request rejected"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class NotFound(DomainError):
    status_code = 404
    default_detail = "Not found"


class Conflict(DomainError):
    status_code = 409
    default_detail = "Conflict"


class Invalid(DomainError):
    status_code = 422
    default_detail = "Invalid request"


class Forbidden(DomainError):
    status_code = 403
    default_detail = "The user doesn't have enough privileges"


async def _handle_domain_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


def register_domain_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
