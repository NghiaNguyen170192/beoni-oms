import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.modules.idempotency.errors import (
    IdempotencyKeyInProgress,
    IdempotencyKeyReused,
)
from app.modules.idempotency.models import SCOPE_KEY_CONSTRAINT, IdempotencyKey


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: Any


def compute_request_hash(payload: Any) -> str:
    """SHA-256 of the canonical JSON form of `payload` (sorted keys, no spaces)."""
    canonical = json.dumps(
        to_jsonable_python(payload), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def lookup(
    session: Session, *, scope: str, key: str, request_hash: str
) -> StoredResponse | None:
    """The stored response for `(scope, key)`, or None on a miss.

    Raises `IdempotencyKeyReused` when the key was stored for a different payload.
    """
    stored = session.exec(
        select(IdempotencyKey).where(
            IdempotencyKey.scope == scope, IdempotencyKey.key == key
        )
    ).first()
    if stored is None:
        return None
    if stored.request_hash != request_hash:
        raise IdempotencyKeyReused()
    return StoredResponse(status_code=stored.response_status, body=stored.response_body)


def store(
    session: Session,
    *,
    scope: str,
    key: str,
    request_hash: str,
    status_code: int,
    body: Any,
) -> None:
    """Stage the key in the caller's transaction and flush. Never commits."""
    session.add(
        IdempotencyKey(
            scope=scope,
            key=key,
            request_hash=request_hash,
            response_status=status_code,
            response_body=to_jsonable_python(body),
        )
    )
    session.flush()


def is_key_conflict(exc: IntegrityError) -> bool:
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None) == SCOPE_KEY_CONSTRAINT


def execute(
    session: Session,
    *,
    scope: str,
    key: str,
    payload: Any,
    operation: Callable[[], tuple[int, Any]],
) -> StoredResponse:
    """Run `operation` at most once per `(scope, key)` and commit.

    `operation` stages its changes without committing and returns
    `(status_code, json_body)`. A repeat returns the stored response; a failed
    operation rolls back and leaves the key unused.
    """
    request_hash = compute_request_hash(payload)
    existing = lookup(session, scope=scope, key=key, request_hash=request_hash)
    if existing is not None:
        return existing

    try:
        status_code, body = operation()
        body = to_jsonable_python(body)
        store(
            session,
            scope=scope,
            key=key,
            request_hash=request_hash,
            status_code=status_code,
            body=body,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if not is_key_conflict(exc):
            raise
        existing = lookup(session, scope=scope, key=key, request_hash=request_hash)
        if existing is None:
            raise IdempotencyKeyInProgress()
        return existing
    except BaseException:
        session.rollback()
        raise
    return StoredResponse(status_code=status_code, body=body)
