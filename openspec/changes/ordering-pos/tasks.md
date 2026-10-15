# Tasks

## 1. Pricing and state machine

- [x] 1.1 Implement `ordering/pricing.py` (line totals, percent/amount discounts, proportional order-discount allocation, tax-inclusive tax amount, VND rounding); verify unit tests for spec examples and edge cases
- [x] 1.2 Implement the transition table and `assert_transition`; verify unit tests for every allowed and a sample of rejected transitions

## 2. Orders backend

- [x] 2.1 Add `orders`, `order_lines`, order-number counter models and migration (status check, RESTRICT FK to menu items, positive quantity); add `tax_rate` to business settings; verify migration round-trip
- [x] 2.2 Implement order service: create, replace/add/update/remove lines with snapshots, discounts with permission and limits, confirm, cancel, idempotent complete with hook steps; verify service tests for each ordering scenario
- [x] 2.3 Add `/orders` routes (create, get, list/search with cashier scoping, lines batch update, discount, confirm, cancel, complete with `Idempotency-Key`); verify API tests for validation, permissions, and conflicts
- [x] 2.4 Verify catalog delete guard now rejects deleting a sold item with an API test

## 3. Frontend

- [x] 3.1 Regenerate client; build POS page (category tabs, item search, cart with quantity steppers, discount dialog gated by permission, order type selector, totals from API, complete button with idempotency key); verify build and lint
- [x] 3.2 Build Order History page (filters, table, detail drawer) and printable receipt route; verify build and lint
- [x] 3.3 Add Playwright spec at tablet viewport: create takeaway order, add items, apply discount as manager, complete, print receipt; cashier sees only own orders; verify spec passes

## 4. Integration check

- [x] 4.1 Change a menu price after completing an order and verify via API test that the completed order totals are unchanged
