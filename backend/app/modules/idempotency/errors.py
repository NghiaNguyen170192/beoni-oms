from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class IdempotencyError(Exception):
    status_code = 400
    detail = "Idempotency error"


class IdempotencyKeyReused(IdempotencyError):
    status_code = 422
    detail = "Idempotency-Key was already used with a different request payload"


class IdempotencyKeyInProgress(IdempotencyError):
    status_code = 409
    detail = "A request with this Idempotency-Key is still being processed; retry later"


async def _handle_idempotency_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, IdempotencyError)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


def register_idempotency_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IdempotencyError, _handle_idempotency_error)
