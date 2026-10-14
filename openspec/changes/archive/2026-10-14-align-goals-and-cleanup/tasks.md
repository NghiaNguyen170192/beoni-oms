# Tasks

## 1. Align goals.md with the chosen stack

- [x] 1.1 Rewrite goals.md sections 1.2, 2.2, 2.6, 3.2, 3.4 and 11.3 to describe the React SPA (TanStack Router/Query, shadcn/ui), the generated OpenAPI client, SQLModel, and `backend/app/modules/<domain>/`; verify `rg -n "Jinja2|HTMX|server-rendered" goals.md` only returns historical/explanatory mentions
- [x] 1.2 Note in goals.md section 11 that the backend remains the source of truth and React never computes authoritative totals; verify by reading the section

## 2. Remove prototype backend code

- [x] 2.1 Confirm any other useful prototype labels (inventory groups such as "Nguyên vật liệu", menu categories such as "Đồ ăn") are listed under seed data in the `catalog-menu` and `inventory-core` designs before deleting; verify by reading those designs
- [x] 2.2 Delete prototype routes (`customers`, `inventory_transactions`, `payments`, `product_ingredients`, `products`, `sales_orders`) and revert `backend/app/api/main.py`; verify `docker compose exec backend python -c "import app.main"` succeeds
- [x] 2.3 Remove prototype models and CRUD additions from `backend/app/models.py` and `backend/app/crud.py`; verify `bash scripts/lint.sh` passes in the backend container

## 3. Remove the template Item sample

- [x] 3.1 Remove `Item*` models, `api/routes/items.py`, item CRUD, `tests/api/routes/test_items.py`, `tests/utils/item.py`, and the `Item` cleanup in `tests/conftest.py`; verify `pytest` passes
- [x] 3.2 Add an Alembic revision that drops the `item` table (downgrade recreates it); verify `alembic upgrade head`, `downgrade -1`, `upgrade head` all succeed

## 4. Clean the frontend

- [x] 4.1 Delete prototype component folders (Customers, Inventory, Payments, Products, SalesOrders, Items), `components/Common/PendingTable.tsx`, `client/oms-client.ts`, and routes `customers`, `inventory`, `payments`, `products`, `sales-orders`, `items`; verify no imports remain with `rg "oms-client|SalesOrders|Items/" frontend/src`
- [x] 4.2 Revert `AppSidebar.tsx` and `client/index.ts` to template navigation (Dashboard, Admin, Settings); regenerate the client with `scripts/generate-client.sh`; verify `bun run build` and `bun run lint` pass
- [x] 4.3 Delete `frontend/tests/items.spec.ts`; verify `bunx playwright test` passes for remaining specs

## 5. Integration check

- [x] 5.1 Run `docker compose up -d --build`, log in as the first superuser, and confirm dashboard, admin, and settings pages load without console errors
