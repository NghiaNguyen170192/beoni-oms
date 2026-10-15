# Tasks

## 1. Module layout and test fixtures

- [x] 1.1 Create `backend/app/modules/__init__.py` and import hook in `app/models.py` so module models are visible to Alembic; verify `alembic check` reports no unexpected diff
- [x] 1.2 Replace the session-scoped delete fixture in `backend/tests/conftest.py` with a per-test transactional session and `get_db` override, plus an `engine`-backed fixture for concurrency tests; verify the existing user/login tests pass unchanged in behavior

## 2. Observability

- [x] 2.1 Add JSON log formatter and request-ID middleware (`X-Request-ID` in/out) in `app/core/logging.py` and `app/main.py`; verify with a test asserting the response header and that the same ID appears in captured logs
- [x] 2.2 Add readiness endpoint `/utils/ready/` returning 503 when `SELECT 1` fails; verify with tests for up and simulated-down database
- [x] 2.3 Add a generic 500 handler that logs the request ID and hides internals; verify with a test route raising an exception

## 3. Identity and permissions

- [x] 3.1 Add `Role` enum, `user.role` column with check constraint, and migration setting superusers to owner; verify migration up/down round-trip
- [x] 3.2 Implement the permission matrix and `require_permission` dependency in `modules/identity/`; verify unit tests cover every role against representative permissions
- [x] 3.3 Allow owners to set roles via user create/update APIs, reject non-owner role changes, include `role` and `permissions` in `/users/me`; verify API tests for allowed, denied, and invalid-role cases
- [x] 3.4 Regenerate the client; add role selector to admin user forms and make `AppSidebar.tsx` filter items by permission; verify a Playwright spec logs in as cashier and inventory_staff and checks visible navigation

## 4. Audit trail

- [x] 4.1 Add `audit_log` table and `audit.record()` helper that never commits; verify a service test showing the entry is present after commit and absent after rollback
- [x] 4.2 Record audit entries for user role changes, activation changes, and settings changes; verify tests assert entries with old/new values
- [x] 4.3 Add owner-only `GET /audit-log` with filters and pagination plus an Audit Log page under admin; verify API permission tests and a Playwright check that the role change appears

## 5. Business settings

- [x] 5.1 Add `business_settings` singleton table seeded with defaults and a service to read/update it; verify defaults test
- [x] 5.2 Add `GET /settings/business` (any authenticated user) and `PUT` (owner only) with timezone/currency validation; verify API tests for read, owner update, manager 403, and invalid timezone
- [x] 5.3 Add a Business tab to the Settings page and a shared VND/date formatting helper in the frontend that reads these settings; verify `bun run build` and a Playwright update test

## 6. Idempotency

- [x] 6.1 Add `idempotency_keys` table with unique `(scope, key)` and helper functions (lookup, store, payload hash check, conflict handling); verify unit/service tests for hit, miss, payload mismatch, and rollback-not-stored
- [x] 6.2 Add an `IdempotencyKey` header dependency that returns 400 when missing; verify with a test route
- [x] 6.3 Add a concurrency test with two sessions inserting the same key, asserting one winner; verify it passes against PostgreSQL

## 7. Language and display names

- [x] 7.1 Add `business_settings.language` (en|vi, check constraint, default en) with migration and owner-only, audited `PUT /settings/business/language`; verify API tests for owner update, manager 403, invalid language, and audit entry
- [x] 7.2 Add `*_name` display fields to audit, movement, adjustment, and order read schemas; verify API tests that names are returned
- [x] 7.3 Add typed en/vi dictionaries and the `useI18n` language store; translate every page, form, toast, and label; show names instead of emails; make Admin a sidebar group with Users, Audit Log, and a Language page; verify build, lint, and a Playwright spec switching to Vietnamese and back

## 8. Integration check

- [x] 8.1 Run full backend suite, `bash scripts/lint.sh`, `bun run lint`, `bun run build`, and Playwright; verify all pass and `docker compose up` starts cleanly
