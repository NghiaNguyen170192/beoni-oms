import threading
import uuid
from decimal import Decimal

from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from app.models import User
from app.modules.accounting import service as accounting
from app.modules.accounting.errors import AdjustmentAlreadyReversed
from app.modules.accounting.ledger import CASH_DRAWER, account_named
from app.modules.accounting.models import CashAdjustment, CashMovement
from app.modules.audit.models import AuditLog
from app.modules.idempotency.models import IdempotencyKey
from app.modules.identity.roles import Role
from tests.utils.db import purge_committed
from tests.utils.user import make_user_with_role


def test_concurrent_reversals_move_cash_once(db_engine: Engine) -> None:
    record_key, reverse_a, reverse_b = (uuid.uuid4().hex for _ in range(3))
    actor_id: uuid.UUID | None = None
    try:
        with Session(db_engine) as session:
            actor = make_user_with_role(session, Role.OWNER)
            account = account_named(session, CASH_DRAWER)
            created = accounting.record_adjustment(
                session,
                account_id=account.id,
                amount=Decimal("500000"),
                reason="opening float",
                actor=actor,
                idempotency_key=record_key,
            )
            adjustment_id = uuid.UUID(created.body["id"])
            actor_id = actor.id

        wins: list[object] = []
        errors: list[BaseException] = []

        def worker(key: str) -> None:
            try:
                with Session(db_engine) as session:
                    user = session.get(User, actor_id)
                    assert user is not None
                    wins.append(
                        accounting.reverse_adjustment(
                            session,
                            adjustment_id=adjustment_id,
                            reason="undo float",
                            actor=user,
                            idempotency_key=key,
                        )
                    )
            except BaseException as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(key,))
            for key in (reverse_a, reverse_b)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert len(wins) == 1
        assert len(errors) == 1
        assert isinstance(errors[0], AdjustmentAlreadyReversed)
        with Session(db_engine) as session:
            reversals = session.exec(
                select(CashAdjustment).where(
                    CashAdjustment.reversal_of_id == adjustment_id
                )
            ).all()
            assert len(reversals) == 1
            movement = session.exec(
                select(CashMovement).where(
                    CashMovement.source_type == "cash_adjustment_reversal",
                    CashMovement.source_id == reversals[0].id,
                )
            ).one()
            assert movement.amount == Decimal("-500000.00")
    finally:
        if actor_id is not None:
            purge_committed(
                db_engine,
                delete(CashMovement).where(CashMovement.actor_id == actor_id),
                delete(CashAdjustment).where(
                    col(CashAdjustment.reversal_of_id).is_not(None),
                    CashAdjustment.recorded_by_id == actor_id,
                ),
                delete(CashAdjustment).where(CashAdjustment.recorded_by_id == actor_id),
                delete(AuditLog).where(AuditLog.actor_id == actor_id),
                delete(IdempotencyKey).where(
                    col(IdempotencyKey.key).in_([record_key, reverse_a, reverse_b])
                ),
                delete(User).where(col(User.id) == actor_id),
            )
