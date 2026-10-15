# Proposal

## Why

Every OMS domain needs the same groundwork: role-based permissions (goals.md section 9), business settings (currency, timezone, negative-stock policy), an audit trail (section 10.3), idempotent operations (section 10.2), and observability (section 12.4). Building these once, before any domain module, keeps later changes small and consistent.

## What Changes

- Add five business roles (Owner/Administrator, Manager, Cashier, Inventory Staff, Accountant) with a fixed permission matrix enforced on every protected API route. The template's `is_superuser` flag maps to Owner.
- Expose the current user's role and permissions to the frontend; the sidebar shows only permitted pages.
- Add business settings (business name, currency VND, timezone `Asia/Ho_Chi_Minh`, allow-negative-stock flag) editable by Owner.
- Add an append-only audit log recording actor, timestamp, entity, action, and a description of changes; viewable by Owner.
- Add idempotency handling: critical operations accept an idempotency key and repeat requests return the original result without side effects.
- Add structured JSON logging with a correlation ID per request (returned in `X-Request-ID`), plus liveness and database readiness health checks.
- Establish the `backend/app/modules/` package layout and PostgreSQL test fixtures used by every later change.

## Capabilities

### New Capabilities

- `identity-access`: roles, permission matrix, backend authorization, and role-aware navigation.
- `business-settings`: business-wide configuration (currency, timezone, negative-stock policy).
- `audit-trail`: append-only record of significant business and permission changes.
- `idempotency`: duplicate-safe processing of critical operations.
- `observability`: request correlation IDs, structured logs, health and readiness checks.

### Modified Capabilities

None (no existing specs).

## Impact

- Backend: new `backend/app/modules/{identity,settings,audit,idempotency}/`, changes to `app/api/deps.py`, `app/main.py` (middleware), `app/api/routes/utils.py` (health), `app/models.py` (User role column), new Alembic migration, new test fixtures in `backend/tests/conftest.py`.
- Frontend: user role in `UserPublic`, permission-aware `AppSidebar.tsx`, Settings page section for business settings, admin user form gains a role selector, regenerated client.
- No new runtime dependencies beyond the standard library (JSON logging via `logging`).
