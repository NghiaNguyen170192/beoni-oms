# Proposal

## Why

The initial release is only successful if it is reliable, recoverable, and verified end to end (goals.md sections 12, 13, Phase 7, and the Definition of Success). This change adds the operational capabilities and the cross-module verification that individual feature changes cannot provide alone.

## What Changes

- Automated daily PostgreSQL backups (plus media files) with retention, and a documented, tested restore procedure.
- An owner-only data integrity check that verifies stock balances against movements, money account balances against cash movements, payables against allocations, and order totals against lines.
- Production hardening: HTTPS-only deployment via the template's Traefik setup, secure headers, restricted CORS, secrets only via environment, no debug/private routes in production.
- Cross-module test suites: the 11-step end-to-end flow from goals.md section 13.4, concurrency and duplicate-request suites, and report reconciliation suites.
- Representative load test against the p95 targets and an authorization boundary review across every route.
- Deployment, backup, restore, and maintenance documentation.

## Capabilities

### New Capabilities

- `data-protection`: backups, restore, and data integrity verification.
- `deployment-security`: production transport, header, CORS, and route exposure rules.

### Modified Capabilities

None.

## Impact

- Infrastructure: `compose.yml` / `compose.traefik.yml` backup service and volumes, `scripts/backup.sh`, `scripts/restore.sh`.
- Backend: `modules/admin/integrity.py` with `/admin/integrity-check`, production settings checks, route-permission audit test.
- Tests: `backend/tests/concurrency/`, `backend/tests/reconciliation/`, `frontend/tests/oms-e2e.spec.ts`, `loadtest/` (k6 or Locust script).
- Docs: `deployment.md`, new sections in `development.md`, and `README.md`.
