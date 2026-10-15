# Proposal

## Why

The defining feature of the system is that a completed sale automatically and correctly deducts the ingredients or products it consumed (goals.md section 6). This connects ordering to inventory, produces cost of goods sold, and must be atomic, idempotent, and safe under concurrent sales.

## What Changes

- Add versioned recipes for prepared menu items: ingredient lines in each item's base unit, effective-from date, active version per item.
- Link direct-sale menu items to one inventory item and quantity per unit sold.
- Calculate consumption on completion: resolve the applicable recipe version, multiply by servings, aggregate per inventory item, check availability, post sale-consumption movements at weighted-average cost, and record recipe version and COGS on each order line, all in the completion transaction.
- Enforce the stock availability policy: reject completion with a list of shortages, or allow negative stock and flag it when the setting is on.
- Add explicit returns to stock for direct-sale items from a completed order, separate from refunds.
- Add a Recipes page and shortage display in POS.

## Capabilities

### New Capabilities

- `recipes`: recipe definitions, versions, effective dates, and direct-sale stock links for menu items.
- `stock-consumption`: automatic inventory deduction and cost capture for completed sales, the stock availability policy, and explicit returns to stock.

### Modified Capabilities

None.

## Impact

- Backend: new `backend/app/modules/recipes/`, migration for `recipes`, `recipe_lines`, `menu_item_stock_links`, `stock_returns`, `stock_return_lines`; new columns on `order_lines` (`recipe_version_id`, `cogs_amount`, `cost_uncertain`); completion step `stock.consume` in `ordering`; permissions `recipes:view`, `recipes:manage`, `inventory:return`.
- Frontend: `routes/_layout/recipes.tsx`, recipe editor, shortage dialog in POS, return-to-stock dialog in order detail.
- Requires `inventory-core`, `catalog-menu`, `ordering-pos`, and `payments-refunds`.
