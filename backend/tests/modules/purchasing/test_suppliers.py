import uuid
from decimal import Decimal

from sqlmodel import Session, func, select

from app.modules.identity.roles import Role
from app.modules.purchasing import service
from app.modules.purchasing.errors import SupplierCodeTaken, SupplierHasReceipts
from app.modules.purchasing.models import Supplier
from app.modules.purchasing.schemas import SupplierCreate, SupplierUpdate
from tests.utils.user import make_user_with_role

D = Decimal


def _supplier(db: Session, actor, **overrides) -> dict:
    payload = {"name": "Trung Nguyên", "phone": "0901000111", **overrides}
    body = service.create_supplier(
        db, data=SupplierCreate.model_validate(payload), actor=actor
    )
    return body.model_dump(mode="json")


def test_create_supplier_is_available(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    body = _supplier(db, staff)
    assert body["name"] == "Trung Nguyên"
    assert body["phone"] == "0901000111"
    assert body["is_active"] is True
    listed, count = service.list_suppliers(db, q="Trung")
    assert count == 1
    assert listed[0].id == uuid.UUID(body["id"])


def test_duplicate_code_rejected(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    _supplier(db, staff, code="TN")
    try:
        _supplier(db, staff, name="Other", code="TN")
        raise AssertionError("expected duplicate code")
    except SupplierCodeTaken:
        pass


def test_deactivated_supplier_rejected_for_new_receipt(db: Session) -> None:
    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    body = _supplier(db, staff)
    updated = service.update_supplier(
        db,
        supplier_id=uuid.UUID(body["id"]),
        data=SupplierUpdate(is_active=False),
        actor=staff,
    )
    assert updated.is_active is False
    assert service.get_supplier(db, updated.id).name == "Trung Nguyên"


def test_supplier_with_receipt_cannot_be_deleted(db: Session) -> None:
    from datetime import date

    from app.modules.inventory.models import Unit
    from app.modules.purchasing.schemas import ReceiptCreate
    from tests.utils.inventory import make_inventory_item

    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    supplier = _supplier(db, staff)
    item = make_inventory_item(db, base_unit=Unit.G, purchase_unit=Unit.KG)
    service.create_receipt(
        db,
        data=ReceiptCreate.model_validate(
            {
                "supplier_id": supplier["id"],
                "receipt_date": date.today().isoformat(),
                "lines": [
                    {
                        "item_id": str(item.id),
                        "purchase_quantity": "1",
                        "purchase_unit_cost": "1000",
                    }
                ],
            }
        ),
        actor=staff,
    )
    try:
        service.delete_supplier(db, supplier_id=uuid.UUID(supplier["id"]), actor=staff)
        raise AssertionError("expected delete rejection")
    except SupplierHasReceipts:
        pass
    assert db.get(Supplier, uuid.UUID(supplier["id"])) is not None


def test_outstanding_balance_sums_unpaid_receipts(db: Session) -> None:
    from datetime import date

    from app.modules.purchasing.models import PayableStatus, SupplierPayable
    from app.modules.purchasing.schemas import ReceiptCreate
    from tests.utils.inventory import make_inventory_item

    staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    supplier = _supplier(db, staff)
    item = make_inventory_item(db)
    for amount in ("1000000", "500000"):
        receipt = service.create_receipt(
            db,
            data=ReceiptCreate.model_validate(
                {
                    "supplier_id": supplier["id"],
                    "receipt_date": date.today().isoformat(),
                    "lines": [
                        {
                            "item_id": str(item.id),
                            "purchase_quantity": "1",
                            "purchase_unit_cost": amount,
                        }
                    ],
                }
            ),
            actor=staff,
        )
        service.post_receipt(
            db,
            receipt_id=receipt.id,
            actor=staff,
            idempotency_key=uuid.uuid4().hex,
        )
    balance = service.supplier_balance(db, uuid.UUID(supplier["id"]))
    assert balance.outstanding == D("1500000.00")
    assert balance.payables_total == D("1500000.00")
    assert balance.paid_total == D("0.00")
    history, count = service.supplier_history(db, uuid.UUID(supplier["id"]))
    assert count == 2
    assert {row.total_value for row in history} == {D("1000000.00"), D("500000.00")}
    assert db.exec(select(func.count()).select_from(SupplierPayable)).one() == 2
    assert all(row.payment_status.value == PayableStatus.UNPAID.value for row in history)
