# Tasks

## 1. Money accounts and ledger

- [ ] 1.1 Add `money_accounts` (seeded) and `cash_movements` models, `payment_methods.account_id`, migration with backfill from existing payments, voids, and refunds; verify migration round-trip and backfill reconciliation test
- [ ] 1.2 Implement `record_money_movement` and hook it into payment, void, and refund services; verify service tests that each event creates exactly one movement in the same transaction
- [ ] 1.3 Implement idempotent cash adjustments with reversal and `/cash` routes (accounts, balances, movements with opening/closing); verify API tests for permissions and balance math

## 2. Expenses

- [ ] 2.1 Add `expense_categories` (seeded) and `expenses` models and migration; verify round-trip
- [ ] 2.2 Implement expense service (record, pay later, reverse, list with category totals) with idempotency and audit; verify service tests for each expenses scenario
- [ ] 2.3 Add `/expenses` routes; verify API tests

## 3. Supplier payments

- [ ] 3.1 Add `supplier_payments` and allocations models and migration; verify round-trip
- [ ] 3.2 Implement supplier payment service (explicit and oldest-first allocation, over-allocation guard, reversal, money movement) and immediate payment on receipt posting; verify service tests for each supplier-payments scenario
- [ ] 3.3 Add supplier payment routes and supplier statement endpoint; verify API tests including receipt reversal now blocked when payments exist

## 4. Financial summary

- [ ] 4.1 Implement timezone-aware period helper and `financial_summary` SQL aggregation plus income listing; verify unit tests for boundary conversion and service tests reproducing each financial-summary scenario
- [ ] 4.2 Add `/finance/summary` and `/finance/income` routes gated by `finance:view`; verify API tests

## 5. Frontend

- [ ] 5.1 Regenerate client; build Expenses page (form, pay-later, reverse, filters, category totals); verify build and lint
- [ ] 5.2 Add supplier payment dialog and statement view on Suppliers page and optional payment on receipt posting; verify build and lint
- [ ] 5.3 Build Cash and Bank page (accounts with "recorded" label, movements, cash adjustment dialog for owner); verify build and lint
- [ ] 5.4 Add Playwright spec: record expense, pay a supplier partially, verify outstanding and cash balances; verify spec passes

## 6. Integration check

- [ ] 6.1 Add an integration test seeding sales, refunds, receipts, payments, and expenses, asserting financial summary and account balances reconcile with source rows
