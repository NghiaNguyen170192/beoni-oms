# Tasks

## 1. Recipes and stock links

- [ ] 1.1 Add `recipes` and `recipe_lines` models (unique item per version, quantity > 0, kind check) and migration; verify migration round-trip
- [ ] 1.2 Implement recipe service: create version (prepared items only), stock-link version (direct_sale only), applicable-version lookup, audit, cost preview; verify service tests for each recipes scenario including future effective date
- [ ] 1.3 Add `/recipes` routes (list by menu item, versions, create version, cost preview); verify API tests for permissions and validation

## 2. Consumption calculation

- [ ] 2.1 Implement pure `aggregate_requirements` with per-line breakdown; verify unit tests for shared ingredients, non-stock items, and fractional quantities
- [ ] 2.2 Add `order_lines` cost columns and `movement_allocations` table migration; verify round-trip

## 3. Deduction on completion

- [ ] 3.1 Implement `stock.consume` completion step (missing-definition check, locking, shortage detection, negative-stock policy, movements, line COGS and version capture); verify service tests for each stock-consumption scenario
- [ ] 3.2 Add structured 409 shortage response in the completion and pay-and-complete routes; verify API tests
- [ ] 3.3 Add PostgreSQL concurrency tests: concurrent last-servings oversell and duplicate completion; verify both pass repeatedly (run 20 iterations)
- [ ] 3.4 Add rollback test injecting a failure after movements are written; verify no movements remain and order is not completed
- [ ] 3.5 Add reconciliation test asserting `sum(line COGS) == sum(sale movement values)` per order

## 4. Returns to stock

- [ ] 4.1 Add `stock_returns` models and migration; implement idempotent returns for direct-sale lines with quantity cap and sellable flag; verify service tests for each returns scenario
- [ ] 4.2 Add `/orders/{id}/stock-returns` routes; verify API tests

## 5. Frontend

- [ ] 5.1 Regenerate client; build Recipes page (menu item list, version history, line editor with inventory search and base unit display, effective date, cost preview); verify build and lint
- [ ] 5.2 Add POS shortage dialog and return-to-stock dialog in order detail; verify build and lint
- [ ] 5.3 Add Playwright spec: create recipe, receive stock, sell, verify inventory decreased by recipe amounts, trigger shortage, return a bottled item; verify spec passes
