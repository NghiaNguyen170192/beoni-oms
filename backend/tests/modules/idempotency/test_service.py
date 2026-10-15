import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import Session, select

from app import crud
from app.models import User, UserCreate
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.errors import IdempotencyKeyReused
from tests.utils.utils import random_email, random_lower_string

SCOPE = "test.create_user"


class Operation:
    """Stages a new user (a stand-in business row) and counts invocations."""

    def __init__(self, db: Session, *, fail: bool = False) -> None:
        self.db = db
        self.fail = fail
        self.calls = 0
        self.email = random_email()

    def __call__(self) -> tuple[int, Any]:
        self.calls += 1
        user = crud.build_user(
            UserCreate(email=self.email, password=random_lower_string())
        )
        self.db.add(user)
        self.db.flush()
        if self.fail:
            raise RuntimeError("insufficient stock")
        return 201, {"id": user.id, "amount": Decimal("45000.00")}


def _users_with(db: Session, email: str) -> list[User]:
    return list(db.exec(select(User).where(User.email == email)).all())


def test_miss_runs_operation_and_stores_response(db: Session) -> None:
    key = str(uuid.uuid4())
    operation = Operation(db)

    result = idempotency.execute(
        db, scope=SCOPE, key=key, payload={"amount": "45000"}, operation=operation
    )

    assert operation.calls == 1
    assert result.status_code == 201
    assert result.body["amount"] == "45000.00"
    stored = idempotency.lookup(
        db,
        scope=SCOPE,
        key=key,
        request_hash=idempotency.compute_request_hash({"amount": "45000"}),
    )
    assert stored == result


def test_hit_returns_original_response_without_side_effects(db: Session) -> None:
    key = str(uuid.uuid4())
    first_op, second_op = Operation(db), Operation(db)

    first = idempotency.execute(
        db, scope=SCOPE, key=key, payload={"amount": 1}, operation=first_op
    )
    second = idempotency.execute(
        db, scope=SCOPE, key=key, payload={"amount": 1}, operation=second_op
    )

    assert second == first
    assert second_op.calls == 0
    assert _users_with(db, second_op.email) == []
    assert len(_users_with(db, first_op.email)) == 1


def test_payload_mismatch_rejected_without_side_effects(db: Session) -> None:
    key = str(uuid.uuid4())
    idempotency.execute(
        db, scope=SCOPE, key=key, payload={"amount": 1}, operation=Operation(db)
    )
    retry = Operation(db)

    with pytest.raises(IdempotencyKeyReused):
        idempotency.execute(
            db, scope=SCOPE, key=key, payload={"amount": 2}, operation=retry
        )

    assert retry.calls == 0
    assert _users_with(db, retry.email) == []


def test_failed_operation_does_not_store_key(db: Session) -> None:
    key = str(uuid.uuid4())
    failing = Operation(db, fail=True)

    with pytest.raises(RuntimeError):
        idempotency.execute(
            db, scope=SCOPE, key=key, payload={"amount": 1}, operation=failing
        )

    assert _users_with(db, failing.email) == []
    request_hash = idempotency.compute_request_hash({"amount": 1})
    assert (
        idempotency.lookup(db, scope=SCOPE, key=key, request_hash=request_hash) is None
    )

    retry = Operation(db)
    result = idempotency.execute(
        db, scope=SCOPE, key=key, payload={"amount": 1}, operation=retry
    )
    assert result.status_code == 201
    assert retry.calls == 1


def test_same_key_in_different_scopes_is_independent(db: Session) -> None:
    key = str(uuid.uuid4())
    a, b = Operation(db), Operation(db)

    idempotency.execute(db, scope="scope.a", key=key, payload={}, operation=a)
    idempotency.execute(db, scope="scope.b", key=key, payload={}, operation=b)

    assert (a.calls, b.calls) == (1, 1)


def test_request_hash_is_canonical() -> None:
    assert idempotency.compute_request_hash(
        {"a": 1, "b": [1, 2]}
    ) == idempotency.compute_request_hash({"b": [1, 2], "a": 1})
    assert idempotency.compute_request_hash(
        {"amount": Decimal("1.00")}
    ) != idempotency.compute_request_hash({"amount": Decimal("1.01")})
