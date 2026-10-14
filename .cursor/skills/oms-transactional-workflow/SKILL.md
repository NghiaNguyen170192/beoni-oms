---
name: oms-transactional-workflow
description: Checklist and code pattern for Beoni OMS critical operations that change stock or money - order completion, payment recording, refunds, stock receipt posting, stock adjustments, supplier payments, and reversals. Use when implementing or reviewing any service that must be atomic, idempotent, and concurrency-safe.
---

# OMS Transactional Workflow

Use this for every operation that writes inventory movements, balances, payments, refunds, payables, or cash movements.

## Checklist

Copy into the task and tick each item:

```text
- [ ] Accepts an idempotency key (header `Idempotency-Key` or body field)
- [ ] Looks up the key first; a repeat returns the original result, no new rows
- [ ] Validates the state transition on the backend (e.g. only DRAFT/CONFIRMED -> COMPLETED)
- [ ] Locks affected rows in deterministic order (sorted by id) with SELECT ... FOR UPDATE
- [ ] Computes quantities/costs on the server with Decimal
- [ ] Appends ledger rows (inventory_movements / cash_movements) referencing the source document
- [ ] Updates balances (quantity, average cost) from the same values written to the ledger
- [ ] Enforces the negative-stock policy from business settings
- [ ] Writes an audit_log entry
- [ ] Single session.commit() at the end; any exception rolls back everything
- [ ] Corrections are new reversing documents; posted rows are never updated in place or deleted
- [ ] Tests: happy path, duplicate request, invalid transition, rollback on failure, concurrency
```

## Pattern

```python
def complete_order(session: Session, *, order_id: UUID, actor: User, idempotency_key: str) -> Order:
    existing = idempotency.find(session, scope="order.complete", key=idempotency_key)
    if existing:
        return session.get(Order, existing.result_id)

    order = session.exec(select(Order).where(Order.id == order_id).with_for_update()).one()
    ordering.assert_transition(order.status, OrderStatus.COMPLETED)

    requirements = recipes.aggregate_requirements(session, order)   # {item_id: Decimal qty}
    balances = inventory.lock_balances(session, sorted(requirements))  # FOR UPDATE, sorted ids
    inventory.check_availability(balances, requirements, settings.allow_negative_stock)

    for item_id, qty in requirements.items():
        inventory.post_movement(session, item_id=item_id, quantity=-qty,
                                source_type="sales_order", source_id=order.id, actor=actor)

    order.status = OrderStatus.COMPLETED
    idempotency.store(session, scope="order.complete", key=idempotency_key, result_id=order.id)
    audit.record(session, actor=actor, entity=order, action="order.completed")
    session.commit()
    return order
```

## Rules

- Idempotency is also enforced by a DB unique constraint on `(scope, key)`, so a race between two identical requests loses on `IntegrityError` and is handled by returning the stored result.
- Lock ordering: always lock the parent document first, then balances sorted by `inventory_item_id`. This avoids deadlocks between concurrent sales.
- Weighted-average cost on receipt: `new_avg = (old_qty * old_avg + in_qty * in_cost) / (old_qty + in_qty)`; consumption uses the current average and stores it on the movement.
- Refunds never restore ingredients. Stock comes back only through an explicit return or adjustment document.
- Never call `session.commit()` inside helpers (`post_movement`, `audit.record`, etc.).

## Required tests (see `oms-testing`)

- Repeating the call with the same key creates no extra movements/payments.
- A forced failure midway leaves zero movements and the original status.
- Two concurrent completions against limited stock: exactly one succeeds when negative stock is disabled.
- After the operation, `balance.quantity == sum(movements.quantity)` for each touched item.
