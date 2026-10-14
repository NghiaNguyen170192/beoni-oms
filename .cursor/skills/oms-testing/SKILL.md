---
name: oms-testing
description: Write and run Beoni OMS tests - pytest unit/integration tests against PostgreSQL, transaction and concurrency tests, reconciliation checks, and Playwright end-to-end specs. Use when adding tests for an OMS change or verifying a change before archiving it.
---

# OMS Testing

## Running

```bash
# backend, inside Compose (uses the real Postgres service)
docker compose up -d db
docker compose exec backend bash scripts/tests-start.sh
docker compose exec backend pytest tests/modules/inventory -x -q

# frontend e2e
docker compose up -d --wait backend
cd frontend && bunx playwright test tests/<spec>.spec.ts
```

Lint/type checks: `docker compose exec backend bash scripts/lint.sh`, `cd frontend && bun run lint`.

## Test layers

| Layer | Location | What |
|---|---|---|
| Unit | `backend/tests/modules/<domain>/test_*_rules.py` | Pure functions: totals, discounts, unit conversion, weighted-average cost, recipe aggregation, state transitions, profit math. No DB. |
| Service integration | `backend/tests/modules/<domain>/test_service.py` | Service functions with a real session: posting, completion, refunds, rollback. |
| API | `backend/tests/modules/<domain>/test_routes.py` | HTTP contract, validation errors, permission denials per role. |
| Concurrency | `backend/tests/concurrency/` | Parallel sessions against Postgres. |
| E2E | `frontend/tests/*.spec.ts` | User workflows through the UI. |

## Fixtures

- Use a per-test transactional session: open a connection, begin, bind a `Session` to it, `yield`, then roll back. Keeps tests isolated without truncating tables.
- Concurrency tests cannot share that transaction; they use independent sessions on `engine` and clean up their own rows.
- Provide factory helpers in `backend/tests/utils/` (`make_inventory_item`, `make_menu_item_with_recipe`, `make_user_with_role`).
- Use `Decimal` literals in assertions (`Decimal("18.0000")`), never floats.

## Concurrency pattern

```python
def test_concurrent_sales_do_not_oversell(seed_item_with_stock):
    item = seed_item_with_stock(quantity=Decimal("18"))  # enough for one coffee
    barrier = threading.Barrier(2)
    results: list[str] = []

    def worker() -> None:
        with Session(engine) as s:
            order = make_order(s, item, qty=1)
            barrier.wait()
            try:
                complete_order(s, order_id=order.id, actor=..., idempotency_key=str(uuid4()))
                results.append("ok")
            except InsufficientStock:
                results.append("rejected")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert sorted(results) == ["ok", "rejected"]
```

## Must-have assertions per critical operation

- Duplicate idempotency key -> same result, no extra rows.
- Injected failure -> no movements, status unchanged.
- `balance.quantity == sum(movement.quantity)` for touched items.
- Reports reconcile with source rows (see `oms-reporting`).

## Playwright

- Log in per role using the existing `auth.setup.ts` approach; add role users via backend seed in local env.
- Prefer `getByRole` / `getByLabel` selectors.
- The end-to-end flow from goals.md section 13.4 lives in `frontend/tests/oms-e2e.spec.ts`.
