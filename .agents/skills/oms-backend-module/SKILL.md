---
name: oms-backend-module
description: Scaffold or extend a Beoni OMS backend domain module (identity, catalog, inventory, purchasing, recipes, ordering, payments, accounting, reporting) in FastAPI + SQLModel. Use when adding tables, services, or API routes for a business domain under backend/app/modules/.
---

# OMS Backend Module

Every business domain lives in its own package under `backend/app/modules/<domain>/`. Follow this layout and these rules so modules stay consistent and testable without HTTP.

## Layout

```text
backend/app/modules/<domain>/
├── __init__.py
├── models.py      # SQLModel table=True classes only
├── schemas.py     # request/response models (Create, Update, Public, ListPublic)
├── service.py     # business use cases; owns the transaction
├── routes.py      # thin FastAPI router; auth + validation + call service
└── errors.py      # optional domain exceptions
```

Tests go in `backend/tests/modules/<domain>/` as `test_service.py` (business rules) and `test_routes.py` (HTTP contract + permissions).

## Models

- Money uses `Decimal` with `sa_type=Numeric(18, 2)`; quantities use `Numeric(18, 4)`. Never use `float` for money or stock.
- Primary keys: `uuid.UUID` with `default_factory=uuid.uuid4`, matching the template's `User` model.
- Timestamps: `DateTime(timezone=True)` with `get_datetime_utc` from `app.models`.
- Statuses are `str` columns backed by a Python `StrEnum` and a DB `CheckConstraint` listing the allowed values.
- Put integrity rules in `__table_args__`: `UniqueConstraint`, `CheckConstraint("quantity > 0")`, foreign keys with explicit `ondelete`.
- Import every module's `models` in `backend/app/models.py` (or `app/core/db.py`) so Alembic autogenerate sees the tables.

```python
class StockReceipt(SQLModel, table=True):
    __tablename__ = "stock_receipts"
    __table_args__ = (
        UniqueConstraint("reference"),
        CheckConstraint("status IN ('draft','posted','reversed')", name="ck_receipt_status"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    reference: str = Field(max_length=64)
    total_value: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 2))
```

## Services

- A service function is one use case: `post_receipt(session, *, receipt_id, actor, idempotency_key)`.
- The service calls `session.commit()` exactly once at the end. Helpers it calls must only `session.add()` / `session.flush()`.
- On any domain error raise a domain exception and let the caller's session roll back; never commit partial work.
- Services receive the actor `User` and write an audit entry via `app.modules.audit.service.record(...)` for changes listed in goals.md section 10.3.
- Critical operations (order completion, payments, refunds, receipt posting, adjustments) must also follow the `oms-transactional-workflow` skill.
- Backend computes all totals, costs, and statuses. Never trust totals sent by the client.

## Routes

- `router = APIRouter(prefix="/<domain-plural>", tags=["<domain>"])`.
- Use `SessionDep` and `CurrentUser` from `app.api.deps`, plus `require_permission("<domain>:<action>")` once the identity module exists.
- Map domain exceptions to `HTTPException` (404 not found, 409 conflict/invalid transition, 422 validation).
- List endpoints accept `skip`/`limit` and return `{ "data": [...], "count": n }` like the template's `ItemsPublic`.
- Register the router in `backend/app/api/main.py`.
- Posted business documents expose `reverse`/`cancel` actions, never `DELETE`.

## After changing models or routes

1. Create a migration with the `oms-alembic-migration` skill.
2. Run backend tests (`oms-testing` skill).
3. Regenerate the frontend client (`oms-frontend-feature` skill).
