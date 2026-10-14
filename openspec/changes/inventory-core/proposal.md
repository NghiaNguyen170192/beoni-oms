# Proposal

## Why

Inventory accuracy is a core principle of goals.md (sections 4 and 10.1): every stock change must be traceable, balances must agree with history, and costs must support COGS later. Receipts, sales deduction, and reports all build on a single movement ledger, so it must exist first.

## What Changes

- Add inventory items: SKU, name, description, category, type (ingredient, merchandise, packaging, consumable), base unit, purchase unit, conversion factor, minimum stock threshold, active flag, optional barcode, timestamps.
- Add an append-only inventory movement ledger; every movement references its originating document and stores quantity in base units and unit cost.
- Add inventory balances (current quantity, weighted-average unit cost, inventory value) maintained only through movements.
- Add stock adjustments (physical count, spoilage, expired, damaged, missing, correction) with previous, change, and resulting quantity, reason, and actor.
- Add low-stock and negative-stock views and movement history per item.
- Add Inventory and Stock Adjustments pages.

## Capabilities

### New Capabilities

- `inventory`: inventory items, units and conversion, balances, weighted-average valuation, and the movement ledger.
- `stock-adjustments`: authorized, reason-coded corrections to stock that post traceable movements.

### Modified Capabilities

None.

## Impact

- Backend: new `backend/app/modules/inventory/` (items, balances, movements, adjustments), migration, permissions `inventory:view`, `inventory:manage`, `inventory:adjust`.
- Frontend: `routes/_layout/inventory.tsx`, `routes/_layout/stock-adjustments.tsx`, `components/Inventory/*`.
- Later changes (`suppliers-stock-receipts`, `recipes-auto-deduction`, `reporting-dashboard`) post and read movements through this module's service functions.
