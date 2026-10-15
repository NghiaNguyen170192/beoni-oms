"""Concurrent completions against PostgreSQL. Each test repeats the race."""

import threading
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Engine
from sqlmodel import Session, col, delete, select

from app.models import User
from app.modules.audit.models import AuditLog
from app.modules.catalog.models import MenuCategory, MenuItem, ProductType
from app.modules.idempotency.models import IdempotencyKey
from app.modules.identity.roles import Role
from app.modules.inventory.models import (
    InventoryBalance,
    InventoryItem,
    InventoryMovement,
    MovementType,
    Unit,
)
from app.modules.ordering import service as ordering
from app.modules.ordering.models import Order, OrderLine, OrderType
from app.modules.ordering.schemas import OrderCreate, OrderLineInput
from app.modules.ordering.states import InvalidTransition
from app.modules.payments.models import Payment, PaymentMethod, PaymentMethodKind
from app.modules.payments.schemas import PaymentCreate
from app.modules.payments.service import record_payment
from app.modules.recipes import service as recipes
from app.modules.recipes.errors import InsufficientStock
from app.modules.recipes.models import MovementAllocation, Recipe, RecipeLine
from app.modules.recipes.schemas import RecipeLineCreate, RecipeVersionCreate
from tests.utils.catalog import make_category, make_menu_item
from tests.utils.db import purge_committed
from tests.utils.inventory import make_inventory_item, seed_stock
from tests.utils.user import make_user_with_role

D = Decimal
ITERATIONS = 20


class _Seed:
    def __init__(self) -> None:
        self.run_id = uuid.uuid4().hex
        self.user_ids: list[uuid.UUID] = []
        self.item_ids: list[uuid.UUID] = []
        self.menu_item_ids: list[uuid.UUID] = []
        self.category_ids: list[uuid.UUID] = []
        self.order_ids: list[uuid.UUID] = []
        self.recipe_ids: list[uuid.UUID] = []
        self.manager_id: uuid.UUID | None = None


def _purge(engine: Engine, seed: _Seed) -> None:
    with Session(engine) as session:
        line_ids = (
            list(
                session.exec(
                    select(OrderLine.id).where(
                        col(OrderLine.order_id).in_(seed.order_ids)
                    )
                ).all()
            )
            if seed.order_ids
            else []
        )
    statements = []
    if line_ids:
        statements.append(
            delete(MovementAllocation).where(
                col(MovementAllocation.order_line_id).in_(line_ids)
            )
        )
    if seed.item_ids:
        statements.append(
            delete(InventoryMovement).where(
                col(InventoryMovement.item_id).in_(seed.item_ids)
            )
        )
        statements.append(
            delete(InventoryBalance).where(
                col(InventoryBalance.item_id).in_(seed.item_ids)
            )
        )
        statements.append(
            delete(InventoryItem).where(col(InventoryItem.id).in_(seed.item_ids))
        )
    if seed.recipe_ids:
        statements.append(
            delete(RecipeLine).where(col(RecipeLine.recipe_id).in_(seed.recipe_ids))
        )
        statements.append(delete(Recipe).where(col(Recipe.id).in_(seed.recipe_ids)))
    if seed.order_ids:
        statements.append(
            delete(Payment).where(col(Payment.order_id).in_(seed.order_ids))
        )
        statements.append(
            delete(OrderLine).where(col(OrderLine.order_id).in_(seed.order_ids))
        )
        statements.append(delete(Order).where(col(Order.id).in_(seed.order_ids)))
    statements.append(
        delete(IdempotencyKey).where(col(IdempotencyKey.key).like(f"{seed.run_id}%"))
    )
    if seed.user_ids:
        statements.append(
            delete(AuditLog).where(col(AuditLog.actor_id).in_(seed.user_ids))
        )
        statements.append(delete(User).where(col(User.id).in_(seed.user_ids)))
    if seed.menu_item_ids:
        statements.append(
            delete(MenuItem).where(col(MenuItem.id).in_(seed.menu_item_ids))
        )
    if seed.category_ids:
        statements.append(
            delete(MenuCategory).where(col(MenuCategory.id).in_(seed.category_ids))
        )
    purge_committed(engine, *statements)


def _paid_order(
    session: Session, seed: _Seed, actor: User, menu_item_id: uuid.UUID, qty: str
) -> uuid.UUID:
    created = ordering.create_order(
        session,
        data=OrderCreate(
            order_type=OrderType.TAKEAWAY,
            lines=[OrderLineInput(menu_item_id=menu_item_id, quantity=D(qty))],
        ),
        actor=actor,
    )
    seed.order_ids.append(created.id)
    method = session.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).first()
    assert method is not None
    record_payment(
        session,
        order_id=created.id,
        data=PaymentCreate(method_id=method.id, amount=created.total),
        actor=actor,
        idempotency_key=f"{seed.run_id}-pay-{created.id}",
    )
    return created.id


def _prepare(
    session: Session, seed: _Seed, stock: str
) -> tuple[User, uuid.UUID, uuid.UUID]:
    from app.modules.settings.service import get_settings

    settings_row = get_settings(session)
    settings_row.allow_negative_stock = False
    session.add(settings_row)
    session.commit()
    manager = make_user_with_role(session, Role.MANAGER)
    seed.user_ids.append(manager.id)
    seed.manager_id = manager.id
    beans = make_inventory_item(
        session,
        base_unit=Unit.G,
        purchase_unit=Unit.G,
        conversion_factor=D("1"),
    )
    seed.item_ids.append(beans.id)
    seed_stock(session, beans, stock, "400")
    category = make_category(session)
    seed.category_ids.append(category.id)
    coffee = make_menu_item(
        session, category=category, product_type=ProductType.PREPARED
    )
    seed.menu_item_ids.append(coffee.id)
    recipe = recipes.create_version(
        session,
        data=RecipeVersionCreate(
            menu_item_id=coffee.id,
            effective_from=datetime.now(timezone.utc) - timedelta(days=1),
            lines=[RecipeLineCreate(inventory_item_id=beans.id, quantity=D("18"))],
        ),
        actor=manager,
    )
    seed.recipe_ids.append(recipe.id)
    return manager, beans.id, coffee.id


def _race(
    engine: Engine, order_ids: list[uuid.UUID], manager_id: uuid.UUID, run_id: str
) -> list[str]:
    barrier = threading.Barrier(len(order_ids), timeout=15)
    results: list[str] = []
    errors: list[BaseException] = []

    def worker(order_id: uuid.UUID, key: str) -> None:
        try:
            with Session(engine) as session:
                actor = session.get(User, manager_id)
                assert actor is not None
                barrier.wait()
                ordering.complete_order(
                    session, order_id=order_id, actor=actor, idempotency_key=key
                )
                results.append("ok")
        except InsufficientStock:
            results.append("short")
        except InvalidTransition:
            results.append("conflict")
        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(order_id, f"{run_id}-complete-{index}"))
        for index, order_id in enumerate(order_ids)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == [], errors
    assert all(not thread.is_alive() for thread in threads)
    return results


def test_concurrent_last_servings_do_not_oversell(db_engine: Engine) -> None:
    for _ in range(ITERATIONS):
        seed = _Seed()
        try:
            with Session(db_engine) as session:
                manager, beans_id, coffee_id = _prepare(session, seed, "18")
                manager_id = manager.id
                first = _paid_order(session, seed, manager, coffee_id, "1")
                second = _paid_order(session, seed, manager, coffee_id, "1")
            results = _race(db_engine, [first, second], manager_id, seed.run_id)
            assert sorted(results) == ["ok", "short"]
            with Session(db_engine) as session:
                balance = session.get(InventoryBalance, beans_id)
                assert balance is not None and balance.quantity == D("0.0000")
                movements = session.exec(
                    select(InventoryMovement).where(
                        InventoryMovement.item_id == beans_id,
                        InventoryMovement.movement_type
                        == MovementType.SALE_CONSUMPTION,
                    )
                ).all()
                assert len(movements) == 1
        finally:
            _purge(db_engine, seed)


def test_concurrent_duplicate_completion_posts_once(db_engine: Engine) -> None:
    for _ in range(ITERATIONS):
        seed = _Seed()
        try:
            with Session(db_engine) as session:
                manager, beans_id, coffee_id = _prepare(session, seed, "100")
                manager_id = manager.id
                order_id = _paid_order(session, seed, manager, coffee_id, "1")
            results = _race(db_engine, [order_id, order_id], manager_id, seed.run_id)
            assert sorted(results) == ["conflict", "ok"]
            with Session(db_engine) as session:
                balance = session.get(InventoryBalance, beans_id)
                assert balance is not None and balance.quantity == D("82.0000")
                movements = session.exec(
                    select(InventoryMovement).where(
                        InventoryMovement.item_id == beans_id,
                        InventoryMovement.movement_type
                        == MovementType.SALE_CONSUMPTION,
                    )
                ).all()
                assert len(movements) == 1
        finally:
            _purge(db_engine, seed)
