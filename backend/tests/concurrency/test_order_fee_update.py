"""Concurrent replacements must keep fee rows and order totals consistent."""

import threading
import uuid
from decimal import Decimal

from sqlalchemy import Engine
from sqlmodel import Session, delete, select

from app.models import User
from app.modules.audit.models import AuditLog
from app.modules.catalog.models import MenuCategory, MenuItem
from app.modules.identity.roles import Role
from app.modules.ordering import service as ordering
from app.modules.ordering.models import Order, OrderFee, OrderLine, OrderType
from app.modules.ordering.schemas import (
    OrderCreate,
    OrderFeeInput,
    OrderFeesReplace,
    OrderLineInput,
)
from app.modules.settings.models import OrderFeeType
from tests.utils.catalog import make_category, make_menu_item
from tests.utils.db import purge_committed
from tests.utils.user import make_user_with_role

D = Decimal
ITERATIONS = 5


def test_concurrent_fee_updates_keep_total_consistent(db_engine: Engine) -> None:
    actor_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    fee_type_id: uuid.UUID | None = None
    try:
        with Session(db_engine) as session:
            actor = make_user_with_role(session, Role.CASHIER)
            actor_id = actor.id
            category = make_category(session)
            category_id = category.id
            item = make_menu_item(session, category=category, price=D("29000"))
            item_id = item.id
            fee_type = OrderFeeType(name=f"Fee {uuid.uuid4().hex}")
            session.add(fee_type)
            session.commit()
            session.refresh(fee_type)
            fee_type_id = fee_type.id
            order = ordering.create_order(
                session,
                data=OrderCreate(
                    order_type=OrderType.TAKEAWAY,
                    lines=[OrderLineInput(menu_item_id=item.id, quantity=D("1"))],
                ),
                actor=actor,
            )
            order_id = order.id

        assert actor_id and fee_type_id and order_id
        for _ in range(ITERATIONS):
            barrier = threading.Barrier(2, timeout=15)
            errors: list[BaseException] = []

            def update(
                amount: Decimal,
                barrier: threading.Barrier,
                errors: list[BaseException],
            ) -> None:
                try:
                    with Session(db_engine) as session:
                        actor = session.get(User, actor_id)
                        assert actor is not None
                        barrier.wait()
                        ordering.replace_fees(
                            session,
                            order_id=order_id,
                            data=OrderFeesReplace(
                                fees=[
                                    OrderFeeInput(
                                        fee_type_id=fee_type_id, amount=amount
                                    )
                                ]
                            ),
                            actor=actor,
                        )
                except BaseException as exc:
                    errors.append(exc)

            threads = [
                threading.Thread(target=update, args=(D("1000"), barrier, errors)),
                threading.Thread(target=update, args=(D("2000"), barrier, errors)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)

            assert errors == [], errors
            assert all(not thread.is_alive() for thread in threads)

        with Session(db_engine) as session:
            order = session.get(Order, order_id)
            fee = session.exec(
                select(OrderFee).where(OrderFee.order_id == order_id)
            ).one()
            assert order is not None
            assert fee.amount in (D("1000"), D("2000"))
            assert order.fee_total == fee.amount
            assert order.total == order.subtotal - order.discount_total + fee.amount
    finally:
        statements = []
        if actor_id is not None:
            statements.extend(
                [
                    delete(AuditLog).where(AuditLog.actor_id == actor_id),
                    delete(User).where(User.id == actor_id),
                ]
            )
        if order_id is not None:
            statements.extend(
                [
                    delete(OrderFee).where(OrderFee.order_id == order_id),
                    delete(OrderLine).where(OrderLine.order_id == order_id),
                    delete(Order).where(Order.id == order_id),
                ]
            )
        if fee_type_id is not None:
            statements.append(delete(OrderFeeType).where(OrderFeeType.id == fee_type_id))
        if item_id is not None:
            statements.append(delete(MenuItem).where(MenuItem.id == item_id))
        if category_id is not None:
            statements.append(
                delete(MenuCategory).where(MenuCategory.id == category_id)
            )
        if statements:
            purge_committed(db_engine, *statements)
