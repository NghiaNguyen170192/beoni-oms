# Tasks

## 1. Categories

- [ ] 1.1 Add `menu_categories` model, migration with seed categories, and service (create, update, reorder, deactivate); verify service tests for create and duplicate-name conflict
- [ ] 1.2 Add `/catalog/categories` routes with `catalog:view` / `catalog:manage`; verify API tests including 403 for cashier writes

## 2. Menu items

- [ ] 2.1 Add `menu_items` model (Numeric price, type and price check constraints, unique code) and migration; verify migration round-trip
- [ ] 2.2 Implement item service (create, update with audit of tracked fields, deactivate, delete guard, search/filter); verify service tests for each spec scenario
- [ ] 2.3 Add `/catalog/items` routes including search params and pagination; verify API tests for validation, conflicts, permissions
- [ ] 2.4 Add image upload endpoint with type/size validation and media volume in `compose.yml`; verify tests for valid upload, oversized, and wrong type

## 3. Frontend

- [ ] 3.1 Regenerate client; build Menu page with category tabs, item DataTable, add/edit dialogs, active/available toggles, and image upload; verify `bun run build` and lint
- [ ] 3.2 Add Playwright spec: manager creates category and item, changes price, marks unavailable; cashier sees read-only menu; verify spec passes

## 4. Integration check

- [ ] 4.1 Confirm the audit log page shows the price change made in the Playwright run; verify manually or via API test
