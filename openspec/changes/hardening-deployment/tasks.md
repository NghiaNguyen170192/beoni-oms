# Tasks

## 1. Integrity check

- [ ] 1.1 Implement integrity queries (stock vs movements, accounts vs cash movements, payables vs allocations, orders vs lines) and owner-only `/admin/integrity-check`; verify tests for clean data, injected drift, and 403 for manager
- [ ] 1.2 Add an Integrity Check panel to the admin page; verify build, lint, and a Playwright check showing zero issues

## 2. Backup and restore

- [ ] 2.1 Add `backup` Compose service, `scripts/backup.sh` with retention, and error reporting on failure; verify a manual run creates dump and media archive and pruning removes old files
- [ ] 2.2 Add `scripts/restore.sh` and run a restore drill into a fresh stack; verify the app serves restored data and the integrity check passes
- [ ] 2.3 Document backup, off-site copy, and restore in `deployment.md`; verify the documented commands match the scripts

## 3. Deployment security

- [ ] 3.1 Make default secrets a startup error in production, add security headers middleware, and confirm private/test-email routes are excluded in production; verify unit tests for config guard and headers
- [ ] 3.2 Add the route-access test enumerating all routes against permissions or `PUBLIC_ROUTES`; verify it passes and fails when an unprotected route is added
- [ ] 3.3 Review Traefik HTTPS redirect and CORS settings for production; verify with `curl -I` against a staging deployment and document results

## 4. Cross-module verification

- [ ] 4.1 Consolidate concurrency suites (oversell, duplicate completion, duplicate payment, duplicate refund, concurrent receipts) under `backend/tests/concurrency/`; verify they pass 20 consecutive runs against PostgreSQL
- [ ] 4.2 Add reconciliation suite seeding a full month of activity and asserting reports, financial summary, account balances, and integrity check agree; verify it passes
- [ ] 4.3 Implement `frontend/tests/oms-e2e.spec.ts` covering the 11 steps of goals.md section 13.4 (item, receipt, recipe, menu item, sale, deduction, payment, COGS, reports, expense, operating profit); verify it passes in CI
- [ ] 4.4 Add k6 load test in `loadtest/` and run it against a seeded stack; verify p95 targets (reads < 500 ms, writes < 1 s, dashboard < 2 s) and record results in `deployment.md`

## 5. Release readiness

- [ ] 5.1 Update `README.md` and `development.md` for OMS setup, roles, and first-run steps; verify a fresh clone can follow them to a working login
- [ ] 5.2 Walk through goals.md section 15 Definition of Success and record evidence (test names, screenshots, or reports) for each item in this change's design.md; verify all 14 items have evidence
