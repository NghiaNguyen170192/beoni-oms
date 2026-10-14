# Proposal

## Why

`goals.md` describes a server-rendered Jinja2/HTMX application, but the project is built on the full-stack-fastapi-template with a React SPA, and the team has decided to keep it. The repository also contains uncommitted prototype OMS code (float money, no movement ledger, no recipe versions, no idempotency) that does not meet the goals and would conflict with the domain modules planned in later changes. Both must be resolved before feature work starts.

## What Changes

- Update `goals.md` so the technology stack, architecture, and web interface sections describe the React SPA + generated OpenAPI client + SQLModel stack and the `backend/app/modules/<domain>/` layout.
- **BREAKING** Remove the prototype OMS backend code: models `InventoryItem`, `RecipeComponent`, `MenuItem`, `InventoryHistoryLog`, `SalesOrder*`; routes `customers`, `inventory_transactions`, `payments`, `product_ingredients`, `products`, `sales_orders`; related `crud.py` additions.
- **BREAKING** Remove the template's sample `Item` feature (model, routes, CRUD, tests, migration-level table via a new drop migration) since OMS domains replace it.
- Remove the prototype React pages and components (Customers, Inventory, Payments, Products, SalesOrders, `oms-client.ts`, `PendingTable`) and the matching sidebar entries; remove the Items page and its Playwright spec.
- Regenerate the frontend client and route tree so the app builds and runs cleanly with only auth, users, settings, and dashboard.

## Capabilities

### New Capabilities

None. This change is documentation and cleanup only (`skip_specs: true`).

### Modified Capabilities

None.

## Impact

- `goals.md`.
- `backend/app/models.py`, `backend/app/crud.py`, `backend/app/api/main.py`, `backend/app/api/routes/*` (prototype routes and `items.py`), `backend/tests/` (items tests and utils), new Alembic migration dropping `item`.
- `frontend/src/client/*`, `frontend/src/components/{Customers,Inventory,Payments,Products,SalesOrders,Items}`, `frontend/src/routes/_layout/*`, `frontend/src/components/Sidebar/AppSidebar.tsx`, `frontend/tests/items.spec.ts`, `frontend/src/routeTree.gen.ts`.
- No production data exists yet, so dropping tables carries no data-migration risk.
