# Tasks

## 1. Suppliers

- [x] 1.1 Add `suppliers` model and migration; implement supplier service (CRUD, deactivate, delete guard); verify service tests for each suppliers scenario
- [x] 1.2 Add `/purchasing/suppliers` routes plus history and balance endpoints; verify API tests including permissions

## 2. Receipts and payables

- [x] 2.1 Add `stock_receipts`, `stock_receipt_lines`, `supplier_payables` models with constraints and migration; verify migration round-trip
- [x] 2.2 Implement draft create/update/delete with backend-computed totals and reference generation; verify service tests for totals, duplicate reference, and draft not touching stock
- [x] 2.3 Implement idempotent atomic posting (conversion, movements, valuation, payable, audit); verify service tests for the coffee example, inactive item rejection, duplicate key, and already-posted conflict
- [x] 2.4 Implement reversal with guards (no applied payments, negative-stock policy) and linking; verify service tests for allowed and rejected reversals
- [x] 2.5 Add `/purchasing/receipts` routes (list/filter, detail, draft CRUD, post, reverse) requiring `Idempotency-Key` on post/reverse; verify API tests

## 3. Frontend

- [x] 3.1 Regenerate client; build Suppliers page (table, form, detail with history and outstanding balance); verify build and lint
- [x] 3.2 Build Stock Receipts page (draft editor with item search, unit display, computed preview, post confirmation, reverse dialog, status/payment badges); verify build and lint
- [x] 3.3 Add Playwright spec: create supplier, draft receipt, post it, verify inventory quantity and supplier balance, reverse it; verify spec passes

## 4. Integration check

- [x] 4.1 Confirm via test or Postgres MCP that payables total equals posted receipts total minus reversals and that balances equal movement sums
