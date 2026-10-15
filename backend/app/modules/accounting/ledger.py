import uuid
from datetime import datetime
from decimal import Decimal

from sqlmodel import Session, select

from app.core.money import money
from app.modules.accounting.errors import AccountNotFound
from app.modules.accounting.models import AccountKind, CashMovement, MoneyAccount
from app.modules.payments.models import PaymentMethodKind

CASH_DRAWER = "Cash drawer"
BANK = "Bank"


def record_money_movement(
    session: Session,
    *,
    account_id: uuid.UUID,
    amount: Decimal,
    occurred_at: datetime,
    source_type: str,
    source_id: uuid.UUID,
    actor_id: uuid.UUID,
    note: str | None = None,
) -> CashMovement:
    """Stage one signed movement. The caller commits."""
    signed = money(amount)
    if signed == 0:
        raise ValueError("A money movement cannot be zero")
    account = session.get(MoneyAccount, account_id)
    if account is None or not account.is_active:
        raise AccountNotFound()
    movement = CashMovement(
        account_id=account_id,
        amount=signed,
        occurred_at=occurred_at,
        source_type=source_type,
        source_id=source_id,
        actor_id=actor_id,
        note=note,
    )
    session.add(movement)
    session.flush()
    return movement


def account_named(session: Session, name: str) -> MoneyAccount:
    account = session.exec(
        select(MoneyAccount).where(MoneyAccount.name == name)
    ).first()
    if account is None:
        raise AccountNotFound(name)
    return account


def default_account(session: Session, kind: PaymentMethodKind) -> MoneyAccount:
    name = CASH_DRAWER if kind == PaymentMethodKind.CASH else BANK
    return account_named(session, name)


def accounts_of_kind(session: Session, kind: AccountKind) -> list[MoneyAccount]:
    return list(
        session.exec(select(MoneyAccount).where(MoneyAccount.kind == kind)).all()
    )
