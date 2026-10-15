import threading
import time
import uuid
from decimal import Decimal

from sqlalchemy import Engine
from sqlmodel import Session, col, delete

from app.modules.inventory import service
from app.modules.inventory.models import (
    InventoryBalance,
    InventoryItem,
    InventoryMovement,
    MovementType,
)
from tests.utils.db import purge_committed
from tests.utils.inventory import (
    assert_reconciled,
    balance_of,
    make_inventory_item,
    seed_stock,
)


def test_concurrent_postings_do_not_overwrite_each_other(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        item_id = make_inventory_item(session).id
        seed_stock(session, session.get(InventoryItem, item_id), "100", "1")  # type: ignore[arg-type]

    start = threading.Barrier(2, timeout=10)
    errors: list[BaseException] = []

    def worker(change: str) -> None:
        try:
            with Session(db_engine) as session:
                start.wait()
                service.post_movements(
                    session,
                    lines=[
                        service.MovementLine(item_id=item_id, quantity=Decimal(change))
                    ],
                    movement_type=MovementType.SALE_CONSUMPTION,
                    source_type="test_concurrency",
                    source_id=uuid.uuid4(),
                    actor=None,
                    allow_negative=False,
                )
                # Hold the row lock so the other posting must wait for it.
                time.sleep(0.3)
                session.commit()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(c,)) for c in ("-10", "-20")]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == []
        with Session(db_engine) as session:
            assert balance_of(session, item_id).quantity == Decimal("70")
            assert_reconciled(session, item_id)
    finally:
        purge_committed(
            db_engine,
            delete(InventoryMovement).where(col(InventoryMovement.item_id) == item_id),
            delete(InventoryBalance).where(col(InventoryBalance.item_id) == item_id),
            delete(InventoryItem).where(col(InventoryItem.id) == item_id),
        )
