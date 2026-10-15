import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, func, select

from app.modules.audit import service as audit
from app.modules.identity.roles import Role
from app.modules.inventory.errors import ItemInactive, NegativeStockNotAllowed
from app.modules.inventory.models import InventoryMovement, MovementType
from app.modules.inventory.schemas import StockAdjustmentCreate
from app.modules.purchasing import service
from app.modules.purchasing.errors import (
    ReceiptAlreadyPosted,
    ReceiptHasPayments,
    ReceiptNotDraft,
    ReceiptReferenceTaken,
)
from app.modules.purchasing.models import PayableStatus, StockReceipt, SupplierPayable
from app.modules.purchasing.schemas import (
    ReceiptCreate,
    ReceiptReverse,
    ReceiptUpdate,
    SupplierCreate,
)
from app.modules.settings import service as settings_service
from tests.utils.inventory import assert_reconciled, balance_of, make_inventory_item
from tests.utils.user import make_user_with_role

D = Decimal


@pytest.fixture(autouse=True)
def disallow_negative_stock(db: Session) -> None:
    row = settings_service.get_settings(db)
    row.allow_negative_stock = False
    db.add(row)
    db.commit()


def _supplier(db: Session, actor) -> uuid.UUID:
    created = service.create_supplier(
        db,
        data=SupplierCreate.model_validate({"name": "Coffee Co", "phone": "0901"}),
        actor=actor,
    )
    return created.id


def _draft(db: Session, actor, supplier_id, item_id, **overrides) -> dict:
    payload = {
        "supplier_id": str(supplier_id),
        "receipt_date": date.today().isoformat(),
        "lines": [
            {
                "item_id": str(item_id),
                "purchase_quantity": "5",
                "purchase_unit_cost": "400000",
            }
        ],
        **overrides,
    }
    body = service.create_receipt(
        db, data=ReceiptCreate.model_validate(payload), actor=actor
    )
    return body.model_dump(mode="json")


def _post(db: Session, actor, receipt_id: str, key: str | None = None) -> dict:
    result = service.post_receipt(
        db,
        receipt_id=uuid.UUID(receipt_id),
        actor=actor,
        idempotency_key=key or uuid.uuid4().hex,
    )
    assert result.status_code == 200
    return result.body  # type: ignore[return-value]


def test_draft_does_not_change_stock(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    before = balance_of(db, item.id).quantity
    _draft(db, staff, _supplier(db, staff), item.id)
    assert balance_of(db, item.id).quantity == before
    assert (
        db.exec(
            select(func.count())
            .select_from(InventoryMovement)
            .where(InventoryMovement.item_id == item.id)
        ).one()
        == 0
    )


def test_duplicate_reference_rejected(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    supplier_id = _supplier(db, staff)
    item = make_inventory_item(db)
    _draft(db, staff, supplier_id, item.id, reference="PN-TEST-1")
    with pytest.raises(ReceiptReferenceTaken):
        _draft(db, staff, supplier_id, item.id, reference="PN-TEST-1")


def test_client_total_is_ignored(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    body = _draft(db, staff, _supplier(db, staff), item.id, total="1")
    assert body["total_value"] == "2000000.00"
    assert body["lines"][0]["line_total"] == "2000000.00"


def test_post_coffee_receipt_converts_and_creates_payable(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    supplier_id = _supplier(db, staff)
    draft = _draft(db, staff, supplier_id, item.id)
    body = _post(db, staff, draft["id"])

    balance = balance_of(db, item.id)
    assert balance.quantity == D("5000.0000")
    assert balance.avg_unit_cost == D("400.0000")
    assert body["status"] == "posted"
    assert body["payment_status"] == "unpaid"
    assert body["lines"][0]["base_qty"] == "5000.0000"
    assert body["lines"][0]["base_unit_cost"] == "400.0000"
    payable = db.exec(
        select(SupplierPayable).where(
            SupplierPayable.receipt_id == uuid.UUID(body["id"])
        )
    ).one()
    assert payable.amount == D("2000000.00")
    assert payable.status == PayableStatus.UNPAID
    [movement] = db.exec(
        select(InventoryMovement).where(
            InventoryMovement.source_id == uuid.UUID(body["id"])
        )
    ).all()
    assert movement.movement_type == MovementType.RECEIPT
    assert movement.quantity == D("5000.0000")
    assert movement.value == D("2000000.00")
    assert_reconciled(db, item.id)


def test_posting_inactive_item_changes_nothing(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    draft = _draft(db, staff, _supplier(db, staff), item.id)
    item.is_active = False
    db.add(item)
    db.commit()
    with pytest.raises(ItemInactive):
        _post(db, staff, draft["id"])
    assert balance_of(db, item.id).quantity == D("0")
    stored = db.get(StockReceipt, uuid.UUID(draft["id"]))
    assert stored is not None and stored.status.value == "draft"
    assert (
        db.exec(
            select(SupplierPayable).where(SupplierPayable.receipt_id == stored.id)
        ).first()
        is None
    )


def test_duplicate_post_key_increases_stock_once(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    draft = _draft(db, staff, _supplier(db, staff), item.id)
    key = uuid.uuid4().hex
    first = _post(db, staff, draft["id"], key)
    second = _post(db, staff, draft["id"], key)
    assert first["id"] == second["id"]
    assert balance_of(db, item.id).quantity == D("5000.0000")
    assert (
        db.exec(
            select(func.count())
            .select_from(InventoryMovement)
            .where(InventoryMovement.source_id == uuid.UUID(draft["id"]))
        ).one()
        == 1
    )


def test_posting_again_with_a_new_key_conflicts(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    draft = _draft(db, staff, _supplier(db, staff), item.id)
    _post(db, staff, draft["id"])
    with pytest.raises(ReceiptAlreadyPosted):
        _post(db, staff, draft["id"])


def test_posted_receipt_cannot_be_edited_or_deleted(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    draft = _draft(db, staff, _supplier(db, staff), item.id)
    _post(db, staff, draft["id"])
    with pytest.raises(ReceiptNotDraft):
        service.update_receipt(
            db,
            receipt_id=uuid.UUID(draft["id"]),
            data=ReceiptUpdate(notes="changed"),
            actor=staff,
        )
    with pytest.raises(ReceiptNotDraft):
        service.delete_receipt(db, receipt_id=uuid.UUID(draft["id"]), actor=staff)


def test_reverse_unpaid_receipt_restores_stock_and_payable(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    item = make_inventory_item(db)
    draft = _draft(db, manager, _supplier(db, manager), item.id)
    posted = _post(db, manager, draft["id"])
    result = service.reverse_receipt(
        db,
        receipt_id=uuid.UUID(posted["id"]),
        data=ReceiptReverse(reason="Wrong delivery"),
        actor=manager,
        idempotency_key=uuid.uuid4().hex,
    )
    assert result.status_code == 200
    body = result.body
    assert body["status"] == "reversed"
    assert body["reversed_by_id"]
    reversal = service.get_receipt(db, uuid.UUID(body["reversed_by_id"]))
    assert reversal.reversal_of_id == uuid.UUID(posted["id"])
    assert balance_of(db, item.id).quantity == D("0")
    assert balance_of(db, item.id).avg_unit_cost == D("0")
    payable = db.exec(
        select(SupplierPayable).where(
            SupplierPayable.receipt_id == uuid.UUID(posted["id"])
        )
    ).one()
    assert payable.amount == D("0")
    assert payable.status == PayableStatus.CANCELLED
    assert service.supplier_balance(db, uuid.UUID(posted["supplier_id"])).outstanding == D(
        "0"
    )
    assert_reconciled(db, item.id)


def test_reverse_paid_receipt_rejected(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    item = make_inventory_item(db)
    draft = _draft(db, manager, _supplier(db, manager), item.id)
    posted = _post(db, manager, draft["id"])
    payable = db.exec(
        select(SupplierPayable).where(
            SupplierPayable.receipt_id == uuid.UUID(posted["id"])
        )
    ).one()
    payable.paid_amount = payable.amount
    payable.status = PayableStatus.PAID
    db.add(payable)
    db.commit()
    with pytest.raises(ReceiptHasPayments):
        service.reverse_receipt(
            db,
            receipt_id=uuid.UUID(posted["id"]),
            data=ReceiptReverse(reason="Too late"),
            actor=manager,
            idempotency_key=uuid.uuid4().hex,
        )
    assert balance_of(db, item.id).quantity == D("5000.0000")


def test_reverse_rejected_when_stock_would_go_negative(db: Session) -> None:
    from app.modules.inventory import service as inventory

    manager = make_user_with_role(db, Role.MANAGER)
    item = make_inventory_item(db)
    draft = _draft(db, manager, _supplier(db, manager), item.id)
    posted = _post(db, manager, draft["id"])
    inventory.post_adjustment(
        db,
        data=StockAdjustmentCreate.model_validate(
            {
                "lines": [
                    {
                        "item_id": str(item.id),
                        "reason": "spoilage",
                        "quantity_change": "-5000",
                    }
                ]
            }
        ),
        actor=manager,
        idempotency_key=uuid.uuid4().hex,
    )
    with pytest.raises(NegativeStockNotAllowed):
        service.reverse_receipt(
            db,
            receipt_id=uuid.UUID(posted["id"]),
            data=ReceiptReverse(reason="No stock left"),
            actor=manager,
            idempotency_key=uuid.uuid4().hex,
        )
    assert balance_of(db, item.id).quantity == D("0")
    payable = db.exec(
        select(SupplierPayable).where(
            SupplierPayable.receipt_id == uuid.UUID(posted["id"])
        )
    ).one()
    assert payable.status == PayableStatus.UNPAID
    assert payable.amount == D("2000000.00")


def test_payables_match_posted_receipts_minus_reversals(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    item = make_inventory_item(db)
    supplier_id = _supplier(db, manager)
    first = _post(db, manager, _draft(db, manager, supplier_id, item.id)["id"])
    second_draft = _draft(
        db,
        manager,
        supplier_id,
        item.id,
        lines=[
            {
                "item_id": str(item.id),
                "purchase_quantity": "1",
                "purchase_unit_cost": "100000",
            }
        ],
    )
    second = _post(db, manager, second_draft["id"])
    service.reverse_receipt(
        db,
        receipt_id=uuid.UUID(second["id"]),
        data=ReceiptReverse(reason="Returned"),
        actor=manager,
        idempotency_key=uuid.uuid4().hex,
    )
    payables = db.exec(
        select(func.coalesce(func.sum(SupplierPayable.amount), 0)).where(
            SupplierPayable.supplier_id == supplier_id,
            SupplierPayable.status != PayableStatus.CANCELLED,
        )
    ).one()
    posted_net = db.exec(
        select(func.coalesce(func.sum(StockReceipt.total_value), 0)).where(
            StockReceipt.supplier_id == supplier_id,
            StockReceipt.status != "draft",
        )
    ).one()
    assert Decimal(payables) == D("2000000.00")
    assert Decimal(posted_net) == D("2000000.00")
    assert_reconciled(db, item.id)
    assert first["total_value"] == "2000000.00"


def test_post_rolls_back_when_audit_fails(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    draft = _draft(db, staff, _supplier(db, staff), item.id)
    real = audit.record

    def boom(*args, **kwargs):
        if kwargs.get("action") == "posted":
            raise RuntimeError("audit failed")
        return real(*args, **kwargs)

    monkeypatch.setattr(audit, "record", boom)
    with pytest.raises(RuntimeError):
        _post(db, staff, draft["id"])
    assert balance_of(db, item.id).quantity == D("0")
    stored = db.get(StockReceipt, uuid.UUID(draft["id"]))
    assert stored is not None and stored.status.value == "draft"
