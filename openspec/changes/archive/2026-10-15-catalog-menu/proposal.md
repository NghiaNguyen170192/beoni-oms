# Proposal

## Why

The POS needs a menu of sellable products with prices before any order can be taken (goals.md section 5.2, Phase 2). Price history must be traceable so that later reports and order snapshots can be trusted.

## What Changes

- Add menu categories (name, sort order, active flag).
- Add menu items with product code, name, description, category, selling price (VND), optional image, active flag, availability flag, and product type: `prepared`, `direct_sale`, or `non_stock`.
- Record every price, name, type, and status change in the audit trail.
- Prevent deletion of menu items once sold; deactivate instead.
- Provide search and filtering for the POS and back office.
- Add a Menu page (categories + items) in the React app.

Linking menu items to inventory (recipes for prepared items, a stock item for direct-sale items) is out of scope here and is delivered by `recipes-auto-deduction`.

## Capabilities

### New Capabilities

- `catalog`: menu categories, menu items, product types, prices, availability, and their change history.

### Modified Capabilities

None.

## Impact

- Backend: new `backend/app/modules/catalog/`, migration for `menu_categories` and `menu_items`, image storage directory mounted as a Compose volume.
- Frontend: `routes/_layout/menu.tsx`, `components/Catalog/*`, sidebar entry gated by `catalog:view`.
- Depends on `platform-foundation` (permissions, audit trail).
