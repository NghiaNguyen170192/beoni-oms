import threading
import uuid
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from app import crud
from app.models import User, UserCreate
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.models import IdempotencyKey
from tests.utils.utils import random_lower_string


def test_concurrent_duplicates_are_processed_once(db_engine: Engine) -> None:
    scope = f"test.concurrency.{uuid.uuid4().hex[:8]}"
    key = str(uuid.uuid4())
    marker = uuid.uuid4().hex
    both_inside = threading.Barrier(2, timeout=10)
    results: list[Any] = []
    errors: list[BaseException] = []

    def worker(n: int) -> None:
        with Session(db_engine) as session:

            def operation() -> tuple[int, Any]:
                user = crud.build_user(
                    UserCreate(
                        email=f"{marker}-{n}@example.com",
                        password=random_lower_string(),
                    )
                )
                session.add(user)
                session.flush()
                # Both requests have missed the lookup and are mid-operation.
                both_inside.wait()
                return 201, {"user_id": user.id}

            try:
                results.append(
                    idempotency.execute(
                        session,
                        scope=scope,
                        key=key,
                        payload={"marker": marker},
                        operation=operation,
                    )
                )
            except BaseException as exc:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(2)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == []
        assert len(results) == 2
        assert results[0] == results[1]
        with Session(db_engine) as session:
            created = session.exec(
                select(User).where(col(User.email).startswith(marker))
            ).all()
            assert len(created) == 1
            assert str(created[0].id) == results[0].body["user_id"]
    finally:
        with Session(db_engine) as session:
            session.exec(
                delete(IdempotencyKey).where(col(IdempotencyKey.scope) == scope)
            )  # type: ignore[call-overload]
            session.exec(delete(User).where(col(User.email).startswith(marker)))  # type: ignore[call-overload]
            session.commit()
