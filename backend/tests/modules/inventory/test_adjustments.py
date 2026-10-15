import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import Session, select

from app.modules.audit.models import AuditLog
from app.modules.identity.roles import Role
from app.modules.inventory import service
from app.modules.inventory.errors import (
    AdjustmentAlreadyReversed,
    ItemInactive,
    NegativeStockNotAllowed,
)
from app.modules.inventory.models import (
    AdjustmentReason,
    InventoryMovement,
    MovementType,
    StockAdjustment,
    Unit,
)
from app.modules.inventory.schemas import StockAdjustmentCreate, StockAdjustmentReverse
from app.modules.settings import service as settings_service
from tests.utils.inventory import (
    assert_reconciled,
    balance_of,
    make_inventory_item,
    seed_stock,
)
from tests.utils.user import make_user_with_role

D = Decimal


@pytest.fixture(autouse=True)
def disallow_negative_stock(db: Session) -> None:
    row = settings_service.get_settings(db)
    row.allow_negative_stock = False
    db.add(row)
    db.commit()


def _adjust(
    db: Session,
    actor: Any,
    *lines: dict[str, Any],
    key: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    data = StockAdjustmentCreate.model_validate({"note": note, "lines": list(lines)})
    result = service.post_adjustment(
        db, data=data, actor=actor, idempotency_key=key or uuid.uuid4().hex
    )
    assert result.status_code == 201
    return result.body  # type: ignore[no-any-return]


def _movements_for(db: Session, source_id: str) -> list[InventoryMovement]:
    return list(
        db.exec(
            select(InventoryMovement).where(
                InventoryMovement.source_id == uuid.UUID(source_id)
            )
        ).all()
    )


def test_spoilage_decreases_stock_and_records_movement(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    milk = make_inventory_item(db, base_unit=Unit.ML, purchase_unit=Unit.L)
    seed_stock(db, milk, "2000", "0.03")

    body = _adjust(
        db, staff, {"item_id": milk.id, "reason": "spoilage", "quantity_change": "-500"}
    )

    assert balance_of(db, milk.id).quantity == D("1500")
    [movement] = _movements_for(db, body["id"])
    assert movement.movement_type == MovementType.ADJUSTMENT
    assert movement.quantity == D("-500")
    assert movement.source_type == "stock_adjustment"
    assert movement.unit_cost == D("0.03")
    assert_reconciled(db, milk.id)


def test_line_records_previous_change_result_reason_and_user(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "2000", "0.5")

    body = _adjust(
        db, staff, {"item_id": beans.id, "reason": "damaged", "quantity_change": "-100"}
    )

    [line] = body["lines"]
    assert (
        line["previous_quantity"],
        line["quantity_change"],
        line["resulting_quantity"],
    ) == (
        "2000.0000",
        "-100.0000",
        "1900.0000",
    )
    assert line["reason"] == "damaged"
    assert body["posted_by_id"] == str(staff.id)
    assert body["posted_at"]


def test_physical_count_posts_the_difference(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "1900", "0.5")

    body = _adjust(
        db,
        staff,
        {"item_id": beans.id, "reason": "physical_count", "counted_quantity": "1850"},
    )

    [line] = body["lines"]
    assert D(line["quantity_change"]) == D("-50")
    assert D(line["resulting_quantity"]) == D("1850")
    assert D(line["counted_quantity"]) == D("1850")
    assert balance_of(db, beans.id).quantity == D("1850")


def test_physical_count_matching_stock_posts_no_movement(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "100", "1")

    body = _adjust(
        db,
        staff,
        {"item_id": beans.id, "reason": "physical_count", "counted_quantity": "100"},
    )

    assert body["lines"][0]["movement_id"] is None
    assert _movements_for(db, body["id"]) == []


def test_increase_without_cost_uses_average(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "1000", "0.6")

    body = _adjust(
        db,
        staff,
        {"item_id": beans.id, "reason": "correction", "quantity_change": "100"},
    )

    assert D(body["lines"][0]["unit_cost"]) == D("0.6")
    balance = balance_of(db, beans.id)
    assert balance.quantity == D("1100") and balance.avg_unit_cost == D("0.6")


def test_increase_with_cost_reaverages(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "1000", "0.5")

    _adjust(
        db,
        staff,
        {
            "item_id": beans.id,
            "reason": "correction",
            "quantity_change": "1000",
            "unit_cost": "0.7",
        },
    )

    assert balance_of(db, beans.id).avg_unit_cost == D("0.6")


def test_one_invalid_line_applies_nothing(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    good = make_inventory_item(db)
    inactive = make_inventory_item(db, is_active=False)
    seed_stock(db, good, "100", "1")
    adjustments_before = len(db.exec(select(StockAdjustment.id)).all())

    with pytest.raises(ItemInactive):
        _adjust(
            db,
            staff,
            {"item_id": good.id, "reason": "missing", "quantity_change": "-10"},
            {"item_id": inactive.id, "reason": "correction", "quantity_change": "5"},
        )

    assert balance_of(db, good.id).quantity == D("100")
    assert len(db.exec(select(StockAdjustment.id)).all()) == adjustments_before
    assert_reconciled(db, good.id)


def test_negative_result_rejected_when_disallowed(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "90", "1")

    with pytest.raises(NegativeStockNotAllowed):
        _adjust(
            db,
            staff,
            {"item_id": beans.id, "reason": "missing", "quantity_change": "-100"},
        )

    assert balance_of(db, beans.id).quantity == D("90")


def test_negative_result_allowed_when_enabled(db: Session) -> None:
    row = settings_service.get_settings(db)
    row.allow_negative_stock = True
    db.add(row)
    db.commit()
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "90", "1")

    _adjust(
        db, staff, {"item_id": beans.id, "reason": "missing", "quantity_change": "-100"}
    )

    assert balance_of(db, beans.id).quantity == D("-10")


def test_duplicate_submission_posts_once(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "100", "1")
    line = {"item_id": beans.id, "reason": "spoilage", "quantity_change": "-10"}

    first = _adjust(db, staff, line, key="dup-key")
    second = _adjust(db, staff, line, key="dup-key")

    assert first == second
    assert len(_movements_for(db, first["id"])) == 1
    assert balance_of(db, beans.id).quantity == D("90")


def test_posting_is_audited(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "100", "1")

    body = _adjust(
        db, staff, {"item_id": beans.id, "reason": "expired", "quantity_change": "-1"}
    )

    entry = db.exec(
        select(AuditLog).where(
            AuditLog.entity_type == "stock_adjustment", AuditLog.entity_id == body["id"]
        )
    ).one()
    assert entry.action == "posted" and entry.actor_id == staff.id


def test_reverse_posts_opposite_movement_and_marks_reversed(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    manager = make_user_with_role(db, Role.MANAGER)
    beans = make_inventory_item(db)
    seed_stock(db, beans, "2000", "0.5")
    body = _adjust(
        db,
        staff,
        {"item_id": beans.id, "reason": "spoilage", "quantity_change": "-100"},
    )

    result = service.reverse_adjustment(
        db,
        adjustment_id=uuid.UUID(body["id"]),
        data=StockAdjustmentReverse(note="counted wrong"),
        actor=manager,
        idempotency_key="rev-1",
    )

    assert result.status_code == 200
    assert result.body["status"] == "reversed"
    assert result.body["reversed_by_id"] == str(manager.id)
    movements = sorted(_movements_for(db, body["id"]), key=lambda m: m.seq or 0)
    assert [(m.movement_type, m.quantity) for m in movements] == [
        (MovementType.ADJUSTMENT, D("-100")),
        (MovementType.REVERSAL, D("100")),
    ]
    assert movements[1].unit_cost == D("0.5")
    assert balance_of(db, beans.id).quantity == D("2000")
    assert_reconciled(db, beans.id)

    repeat = service.reverse_adjustment(
        db,
        adjustment_id=uuid.UUID(body["id"]),
        data=StockAdjustmentReverse(note="counted wrong"),
        actor=manager,
        idempotency_key="rev-1",
    )
    assert repeat.body == result.body
    with pytest.raises(AdjustmentAlreadyReversed):
        service.reverse_adjustment(
            db,
            adjustment_id=uuid.UUID(body["id"]),
            data=StockAdjustmentReverse(),
            actor=manager,
            idempotency_key="rev-2",
        )


@pytest.mark.parametrize(
    "line",
    [
        {"reason": "spoilage", "quantity_change": "10"},
        {"reason": "correction", "quantity_change": "0"},
        {"reason": "correction"},
        {"reason": "physical_count"},
        {"reason": "physical_count", "counted_quantity": "-1"},
        {"reason": "physical_count", "counted_quantity": "5", "quantity_change": "1"},
        {"reason": "missing", "quantity_change": "-1", "unit_cost": "2"},
    ],
)
def test_invalid_lines_rejected(line: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        StockAdjustmentCreate.model_validate(
            {"lines": [{"item_id": uuid.uuid4(), **line}]}
        )


def test_duplicate_item_in_one_adjustment_rejected() -> None:
    item_id = uuid.uuid4()
    line = {
        "item_id": item_id,
        "reason": AdjustmentReason.CORRECTION,
        "quantity_change": "1",
    }
    with pytest.raises(ValueError):
        StockAdjustmentCreate.model_validate({"lines": [line, line]})
