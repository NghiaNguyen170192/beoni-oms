# Tasks: Batch Production and Finished-Goods Inventory

## 1. Domain and migration

- [x] 1.1 Inspect current inventory item, recipe-version, inventory movement/balance, menu product, order-line, payment, return, costing, and idempotency models; document reuse decisions before coding.
- [x] 1.2 Add or formalize inventory item classification for raw materials and finished goods, preserving existing records and defaults.
- [x] 1.3 Extend/reuse versioned recipes so one formula can consume multiple raw materials and produce multiple finished/menu items.
- [x] 1.4 Add production batch run-multiplier and batch-level cost fields, plus ingredient/output/lot persistence models with constraints and indexes.
- [x] 1.5 Update Alembic migration(s) for the run multiplier and batch-level cost fields; preserve registered models and existing data.
- [x] 1.6 Add an audited migration/opening-stock workflow for existing menu items; do not fabricate historical batches.

## 2. Production service and API

- [x] 2.1 Implement batch draft creation, listing, filtering by formula/output menu item, detail, and draft-only updates.
- [x] 2.2 Implement reusable formula selection; scale ingredient snapshots by formula runs and allow independently selected output products/quantities per batch.
- [x] 2.3 Implement batch completion atomically: consume inputs, receive selected good outputs, record waste/finished time, and store total consumed-material cost without per-item allocation.
- [x] 2.4 Add idempotent completion and safe reversal/correction behavior using existing idempotency patterns.
- [x] 2.5 Add optional start/in-progress workflow only if it is needed by the current UX; otherwise keep draft-to-completed simple.
- [x] 2.6 Add production permissions, backdating permission, reversal permission, and traceability permission.
- [ ] 2.7 Add API tests for invalid states, insufficient materials, unit conversions, multi-output batches, backdating, duplicate requests, rollback, permission failures, and concurrent completions.

## 3. Finished-goods inventory and POS

- [x] 3.1 Expose finished-goods on-hand and lot balances in inventory queries and UI.
- [x] 3.2 Implement deterministic FEFO/FIFO lot allocation for POS order lines, supporting a line fulfilled from multiple lots.
- [x] 3.3 Change POS/order completion so tracked menu goods deduct finished-goods lots only; do not call recipe ingredient consumption from POS.
- [x] 3.4 Keep payment, order completion, lot deduction, allocation persistence, and COGS handling in the existing atomic/idempotent order-completion flow; leave COGS uncertain when no per-item lot cost exists.
- [x] 3.5 Reject insufficient finished-goods stock even when global negative stock is enabled; never silently deduct raw materials as fallback.
- [ ] 3.6 Add tests proving POS completion changes finished-goods balance but leaves raw-material balances unchanged.
- [ ] 3.7 Add concurrency and idempotency tests proving two concurrent sales cannot oversell stock and retries cannot deduct twice.

## 4. Returns and traceability

- [x] 4.1 Persist lot allocations from each completed order line to its source batch/output lot.
- [x] 4.2 Update order detail and return flows to show original batch/lot and finished date.
- [x] 4.3 Validate return quantities against sold quantity less prior returns.
- [x] 4.4 Return accepted, sellable items to their original lot; record unsellable items as waste/non-sellable stock without restoring sellable balance.
- [x] 4.5 Add traceability query showing batch ingredients, outputs, remaining stock, orders, and returns.
- [ ] 4.6 Add tests for multi-lot sale, partial return, repeated return attempts, sellable/unsellable disposition, and traceability continuity.

## 5. React UI and OpenAPI client

- [x] 5.1 Add production batch list and filters.
- [x] 5.2 Add batch create/edit/detail screens with planned versus actual ingredient/output quantities, waste, and finished date/time.
- [x] 5.3 Add finished-goods lot details to inventory item views.
- [x] 5.4 Update POS stock availability/shortage UI to reflect finished-goods stock only.
- [x] 5.5 Update order/return detail to display batch traceability.
- [x] 5.6 Regenerate the generated OpenAPI TypeScript client and update frontend types/usages.
- [ ] 5.7 Add Playwright coverage for create batch -> complete batch -> POS sale -> return -> verify source batch.

## 6. Reports, costing, and release safety

- [x] 6.1 Ensure inventory movement and stock-status reports include finished goods and lot-level movements.
- [x] 6.2 Report total batch material cost as a production expense on the finished date and include it in operating profit; do not derive per-item costs, and keep sale COGS uncertainty explicit.
- [x] 6.3 Add batch production report by date, product, batch status, planned/actual yield, and waste.
- [x] 6.4 Verify timezone handling for production/finished dates in Asia/Ho_Chi_Minh and date-boundary reports.
- [ ] 6.5 Run the full backend test suite and Playwright suite against PostgreSQL; fix regressions in inventory, recipes, purchasing, POS, returns, accounting, and reporting.
- [x] 6.6 Document rollout, initial finished-goods stock count, rollback limits, and operator workflow.
