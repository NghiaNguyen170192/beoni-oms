import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import User
from app.modules.identity.roles import Role
from app.modules.ordering import service
from app.modules.ordering.models import Order, OrderFee, OrderType
from app.modules.ordering.schemas import OrderCreate
from app.modules.settings.models import OrderFeeType
from tests.utils.user import make_user_with_role

D = Decimal


def test_order_fee_type_and_snapshot_persist(db: Session) -> None:
    cashier: User = make_user_with_role(db, Role.CASHIER)
    order_public = service.create_order(
        db, data=OrderCreate(order_type=OrderType.TAKEAWAY), actor=cashier
    )
    assert order_public.fee_total == D("0")
    assert order_public.fees == []
    order = db.get(Order, order_public.id)
    assert order is not None
    fee_type = OrderFeeType(name="Shipping")
    db.add(fee_type)
    db.commit()

    fee = OrderFee(
        order_id=order.id,
        fee_type_id=fee_type.id,
        fee_name=fee_type.name,
        amount=D("25000"),
    )
    order.fee_total = D("25000")
    order.total = D("25000")
    db.add(order)
    db.add(fee)
    db.commit()

    saved = db.exec(select(OrderFee).where(OrderFee.order_id == order.id)).one()
    assert (saved.fee_type_id, saved.fee_name, saved.amount) == (
        fee_type.id,
        "Shipping",
        D("25000.00"),
    )
    public = service.get_order(db, order_id=order.id, actor=cashier)
    assert public.fee_total == public.total == D("25000.00")
    assert [(row.fee_type_id, row.fee_name, row.amount) for row in public.fees] == [
        (fee_type.id, "Shipping", D("25000.00"))
    ]


def test_order_fee_rejects_duplicate_type_for_order(db: Session) -> None:
    cashier = make_user_with_role(db, Role.CASHIER)
    order = service.create_order(
        db, data=OrderCreate(order_type=OrderType.TAKEAWAY), actor=cashier
    )
    fee_type = OrderFeeType(name="Shipping")
    db.add(fee_type)
    db.commit()
    db.add_all(
        [
            OrderFee(
                order_id=order.id,
                fee_type_id=fee_type.id,
                fee_name="Shipping",
                amount=D("1000"),
            ),
            OrderFee(
                order_id=order.id,
                fee_type_id=fee_type.id,
                fee_name="Shipping",
                amount=D("2000"),
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db.commit()


def test_order_fee_rejects_non_positive_amount(db: Session) -> None:
    cashier = make_user_with_role(db, Role.CASHIER)
    order = service.create_order(
        db, data=OrderCreate(order_type=OrderType.TAKEAWAY), actor=cashier
    )
    fee_type = OrderFeeType(name="Shipping")
    db.add(fee_type)
    db.commit()
    db.add(
        OrderFee(
            order_id=order.id,
            fee_type_id=fee_type.id,
            fee_name="Shipping",
            amount=D("0"),
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()


def test_order_fee_rejects_unknown_fee_type(db: Session) -> None:
    cashier = make_user_with_role(db, Role.CASHIER)
    order = service.create_order(
        db, data=OrderCreate(order_type=OrderType.TAKEAWAY), actor=cashier
    )
    db.add(
        OrderFee(
            order_id=order.id,
            fee_type_id=uuid.uuid4(),
            fee_name="Shipping",
            amount=D("1000"),
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()
