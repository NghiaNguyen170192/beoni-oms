# Tasks

## 1. Categories

- [x] 1.1 Add `menu_categories` model, migration with seed categories, and service (create, update, reorder, deactivate); verify service tests for create and duplicate-name conflict
- [x] 1.2 Add `/catalog/categories` routes with `catalog:view` / `catalog:manage`; verify API tests including 403 for cashier writes

## 2. Menu items

- [x] 2.1 Add `menu_items` model (Numeric price, type and price check constraints, unique code) and migration; verify migration round-trip
- [x] 2.2 Implement item service (create, update with audit of tracked fields, deactivate, delete guard, search/filter); verify service tests for each spec scenario
- [x] 2.3 Add `/catalog/items` routes including search params and pagination; verify API tests for validation, conflicts, permissions
- [x] 2.4 Add image upload endpoint with type/size validation and media volume in `compose.yml`; verify tests for valid upload, oversized, and wrong type

## 3. Frontend

- [x] 3.1 Regenerate client; build Menu page with category tabs, item DataTable, add/edit dialogs, active/available toggles, and image upload; verify `bun run build` and lint
- [x] 3.2 Add Playwright spec: manager creates category and item, changes price, marks unavailable; cashier sees read-only menu; verify spec passes

## 4. System-assigned codes

- [x] 4.1 Add sequence `menu_item_code_seq` (migration) and assign `MENU-NNNNN` on create; remove `code` from create/update payloads; verify service and API tests for sequential codes and ignored code edits
- [x] 4.2 Show the code read-only in the Menu page and drop the code input; update the Playwright spec; verify it passes

## 5. Integration check

- [x] 5.1 Confirm the audit log page shows the price change made in the Playwright run; verify manually or via API test
