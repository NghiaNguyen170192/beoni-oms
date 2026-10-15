import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session, select

from app.modules.audit import service as audit
from app.modules.audit.models import AuditLog
from app.modules.identity.roles import Role
from tests.utils.user import make_user_with_role


def _entries_for(db: Session, entity_id: str) -> list[AuditLog]:
    return list(db.exec(select(AuditLog).where(AuditLog.entity_id == entity_id)).all())


def test_entry_is_present_after_commit(db: Session) -> None:
    actor = make_user_with_role(db, Role.OWNER)
    entity_id = str(uuid.uuid4())

    audit.record(
        db,
        actor=actor,
        entity_type="order",
        entity_id=entity_id,
        action="completed",
        changes={"total": {"old": None, "new": Decimal("45000.00")}},
    )
    db.commit()

    [entry] = _entries_for(db, entity_id)
    assert entry.actor_id == actor.id
    assert entry.entity_type == "order"
    assert entry.action == "completed"
    assert entry.occurred_at.tzinfo is not None
    assert entry.changes == {"total": {"old": None, "new": "45000.00"}}


def test_entry_is_absent_after_rollback(db: Session) -> None:
    actor = make_user_with_role(db, Role.OWNER)
    entity_id = str(uuid.uuid4())

    audit.record(
        db, actor=actor, entity_type="order", entity_id=entity_id, action="completed"
    )
    db.rollback()

    assert _entries_for(db, entity_id) == []


def test_record_does_not_commit(db: Session) -> None:
    actor = make_user_with_role(db, Role.OWNER)
    entry = audit.record(
        db, actor=actor, entity_type="order", entity_id="x", action="completed"
    )

    assert entry in db.new


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_log SET action = 'tampered' WHERE id = %s",
        "DELETE FROM audit_log WHERE id = %s",
    ],
)
def test_audit_log_is_append_only_in_database(db: Session, statement: str) -> None:
    actor = make_user_with_role(db, Role.OWNER)
    entry = audit.record(
        db, actor=actor, entity_type="order", entity_id="y", action="completed"
    )
    db.commit()

    with pytest.raises(DBAPIError, match="append-only"):
        db.connection().exec_driver_sql(statement, (entry.id,))
    db.rollback()


def test_diff_reports_only_changed_fields() -> None:
    changes = audit.diff(
        {"role": Role.CASHIER, "is_active": True},
        {"role": Role.MANAGER, "is_active": True},
        ["role", "is_active"],
    )

    assert changes == {"role": {"old": "cashier", "new": "manager"}}
