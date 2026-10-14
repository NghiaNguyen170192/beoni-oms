# Design

## Context

The template provides JWT bearer auth (`app/api/deps.py`: `CurrentUser`, `get_current_active_superuser`), a `User` SQLModel with `is_superuser`, a trivial `/utils/health-check/`, Sentry SDK wiring, and a session-scoped test fixture that deletes rows after the run. There is no role model, settings table, audit log, or request correlation.

## Goals / Non-Goals

**Goals:**
- Reusable building blocks (`require_permission`, `audit.record`, `idempotency` helpers, transactional test session) that every later module imports.
- Establish `backend/app/modules/` and its conventions (see `oms-backend-module` skill).

**Non-Goals:**
- Per-user custom permissions or editable role definitions (fixed matrix for v1).
- Multi-business / multi-branch tenancy.
- Switching from bearer tokens to cookie sessions.

## Decisions

- **Role column on `user`, fixed permission map in code.** `role` is a `str` column with a check constraint; `PERMISSIONS: dict[Role, frozenset[str]]` lives in `modules/identity/permissions.py`. Permission strings follow `<domain>:<action>` (e.g. `inventory:adjust`, `reports:financial`). Alternative: role/permission tables - rejected as unnecessary for five fixed roles; can migrate later without API change.
- **`require_permission(perm)` FastAPI dependency** returning the `User`; superuser always passes. Routes declare it via `dependencies=[...]` or as a parameter.
- **Bearer tokens remain; CSRF not applicable.** The SPA sends `Authorization: Bearer`, not cookies, so CSRF protection (goals.md 9.2) is satisfied by design. Document this; revisit only if cookies are introduced.
- **Settings as a singleton table** (`business_settings`, one row, id=1, seeded by migration). Read via a cached-per-request service function.
- **Audit log** table `audit_log(id, actor_id, occurred_at, entity_type, entity_id, action, changes JSONB, request_id)`. `audit.record(session, ...)` only `add()`s - the caller's commit makes it atomic with the business change.
- **Idempotency** table `idempotency_keys(scope, key, request_hash, response_status, response_body JSONB, created_at)` with unique `(scope, key)`. Helper used inside services: lookup first; on miss run the operation and insert the key in the same transaction; on `IntegrityError` from a concurrent duplicate, roll back and return the stored response (or 409 if not yet visible). Request hash = SHA-256 of the canonical JSON body to detect payload mismatch. Keys older than 7 days may be purged by a maintenance task.
- **Logging**: a stdlib `logging` JSON formatter plus a middleware that sets a `contextvars` request ID. No new dependency.
- **Health**: keep `/utils/health-check/` as liveness; add `/utils/ready/` that runs `SELECT 1`.
- **Test fixtures**: replace the delete-all fixture with a per-test connection + outer transaction + `Session(bind=connection, join_transaction_mode="create_savepoint")`; the `TestClient` overrides `get_db` with it. Concurrency tests get a separate `engine`-backed fixture.

## Risks / Trade-offs

- [Fixed permission matrix may not fit every shop] → Matrix is data in one file; editable roles can be a later change.
- [Idempotency rows grow unbounded] → Purge task for keys older than the retention window.
- [Changing the test fixture breaks template tests] → Migrate existing user/login tests in the same group and run the full suite.

## Migration Plan

- Alembic revision adds `user.role` (default `cashier`, superusers set to `owner`), `business_settings` (seeded row), `audit_log`, `idempotency_keys`.
- Rollback: downgrade drops the new tables and column; no existing data is lost.
