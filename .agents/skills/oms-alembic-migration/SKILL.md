---
name: oms-alembic-migration
description: Generate, review, and apply Alembic migrations for the Beoni OMS backend (SQLModel + PostgreSQL in Docker Compose). Use after adding or changing SQLModel tables, constraints, or indexes.
---

# OMS Alembic Migration

Migrations live in `backend/app/alembic/versions/`. The Compose service is `backend`; the database service is `db`.

## Steps

1. Make sure the new module's models are imported where Alembic's `env.py` can see them (`app.models` imports each `app.modules.<domain>.models`).
2. Start the stack: `docker compose up -d db backend` (or `docker compose watch`).
3. Generate:

   ```bash
   docker compose exec backend alembic revision --autogenerate -m "add stock receipts"
   ```

4. Review the generated file by hand. Autogenerate commonly misses or mangles:
   - `CheckConstraint`s (statuses, positive quantities, non-negative money) - add with `op.create_check_constraint`.
   - Partial or composite unique indexes (idempotency `(scope, key)`, document references).
   - `Numeric(18, 2)` / `Numeric(18, 4)` precision - confirm it is not `Float`.
   - Server defaults and enum value changes.
   - Data migrations (seed roles, payment methods, expense categories) - write them explicitly with `op.bulk_insert`.
   - `sqlmodel.sql.sqltypes.AutoString` needs `import sqlmodel` at the top of the file.
5. Ensure `downgrade()` reverses everything in `upgrade()`.
6. Apply and verify round-trip:

   ```bash
   docker compose exec backend alembic upgrade head
   docker compose exec backend alembic downgrade -1
   docker compose exec backend alembic upgrade head
   ```

7. Optionally confirm the schema with the Postgres MCP (`\d stock_receipts` equivalent / list constraints).

## Rules

- One migration per OpenSpec change where practical; name it after the change.
- Never edit a migration that has been applied on a shared/production database; add a new one.
- Never drop columns that hold posted financial or inventory history without a data-preserving plan.
