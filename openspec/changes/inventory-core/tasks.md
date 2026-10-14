# Tasks

## 1. Inventory items

- [ ] 1.1 Add `inventory_items` and `inventory_balances` models with constraints (unique SKU/barcode, factor > 0) and migration with seed categories; verify migration round-trip
- [ ] 1.2 Implement item service (create with zero balance, update without quantity/cost, deactivate, delete guard, search) and unit-conversion helper; verify unit tests for conversion and service tests for each item scenario
- [ ] 1.3 Add `/inventory/items` routes with permissions; verify API tests for validation, conflicts, and 403s

## 2. Movement ledger and valuation

- [ ] 2.1 Add `inventory_movements` model (signed quantity, unit_cost, type, source_type/source_id, cost_uncertain, actor) and migration; verify migration round-trip
- [ ] 2.2 Implement `post_movements` with sorted `FOR UPDATE` locking, weighted-average rules, negative-stock policy, and no commit; verify unit tests for average-cost math (including zero/negative prior balance) and service tests for balance == movement sum
- [ ] 2.3 Add concurrency test posting simultaneous movements on one item; verify final quantity is correct against PostgreSQL
- [ ] 2.4 Add `/inventory/items/{id}/movements` (filters, running balance) plus low-stock and negative-stock list endpoints; verify API tests

## 3. Stock adjustments

- [ ] 3.1 Add `stock_adjustments` and lines models (reason check constraint, previous/change/result) and migration; verify round-trip
- [ ] 3.2 Implement idempotent atomic adjustment posting (including physical count difference) and reversal with audit; verify service tests for every stock-adjustments scenario including duplicate key and all-or-nothing
- [ ] 3.3 Add `/inventory/adjustments` routes (list, detail, post, reverse) requiring `Idempotency-Key` on post/reverse; verify API tests for permissions and negative-stock rejection

## 4. Frontend

- [ ] 4.1 Regenerate client; build Inventory page (item table with quantity, unit, avg cost, value, low/negative badges, filters; item form; movement history drawer); verify build and lint
- [ ] 4.2 Build Stock Adjustments page (multi-line form with reason, count mode, confirmation dialog, list with reverse action); verify build and lint
- [ ] 4.3 Add Playwright spec: create item, post spoilage, see movement and low-stock badge, reverse it; verify spec passes

## 5. Integration check

- [ ] 5.1 Use the Postgres MCP or a test to confirm `quantity == sum(movements)` for all items after the Playwright run
