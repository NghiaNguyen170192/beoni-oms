# Proposal

## Why

Stock enters the business through supplier purchases (goals.md sections 4.4 and 4.5). Receipts must convert purchase units, increase stock, update weighted-average cost, and create a supplier payable, while drafts stay side-effect free and posted receipts are corrected only by reversal.

## What Changes

- Add suppliers with contact details, active flag, and a view of purchase history and outstanding balance.
- Add stock receipts with reference, supplier, receipt date, lines (item, purchase quantity, purchase unit cost), total value, notes, responsible user, and status `draft` → `posted` → `reversed`.
- Posting converts quantities to base units, posts receipt movements, updates valuation, and records a supplier payable for the receipt total.
- Reversal posts opposite movements and cancels the remaining payable, only if stock and payments allow it.
- Add Suppliers and Stock Receipts pages.

Supplier payments (paying payables, including payment at receipt time) are delivered by `accounting-basic`; until then every posted receipt shows payment status `unpaid`.

## Capabilities

### New Capabilities

- `suppliers`: supplier records, purchase history, and outstanding balances.
- `stock-receipts`: draft, posting, and reversal of supplier stock receipts and their payables.

### Modified Capabilities

None.

## Impact

- Backend: new `backend/app/modules/purchasing/` (suppliers, receipts, payables), migration, permissions `purchasing:view`, `purchasing:manage`, `purchasing:post`, `purchasing:reverse`.
- Uses `inventory.post_movements` and idempotency from earlier changes.
- Frontend: `routes/_layout/suppliers.tsx`, `routes/_layout/stock-receipts.tsx`, `components/Purchasing/*`.
