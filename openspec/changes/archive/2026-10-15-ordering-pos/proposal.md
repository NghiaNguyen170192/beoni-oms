# Proposal

## Why

Selling is the center of the product (goals.md section 5). Cashiers need a fast POS to build orders, while the backend must own totals, validate state transitions, and snapshot prices so history never changes when the menu does.

## What Changes

- Add orders with a generated unique order number, order type (counter, takeaway, dine_in with optional table label), notes, cashier, and timestamps.
- Add order lines that snapshot menu item id, name, unit price, quantity, discount, tax, and line total at the time they are added.
- Backend-calculated subtotal, discounts, tax, and total; line and order discounts by amount or percentage, gated by a discount permission.
- An order state machine (draft, confirmed, paid, completed, cancelled, partially_refunded, refunded) enforced on the backend; this change implements draft, confirmed, completed, and cancelled transitions.
- Printable receipt view and order history search.
- POS page optimized for desktop and tablet, plus an Order History page.

Payments, paid/refund states, and the "completion requires payment" rule come in `payments-refunds`. Stock deduction on completion comes in `recipes-auto-deduction`.

## Capabilities

### New Capabilities

- `ordering`: orders, lines with price snapshots, discounts, totals, lifecycle, receipts, and order history.

### Modified Capabilities

None.

## Impact

- Backend: new `backend/app/modules/ordering/`, migration for `orders` and `order_lines`, permissions `ordering:create`, `ordering:view_own`, `ordering:view_all`, `ordering:discount`, `ordering:cancel`.
- Adds `ON DELETE RESTRICT` from order lines to menu items, activating the catalog "sold items cannot be deleted" guard.
- Frontend: `routes/_layout/pos.tsx`, `routes/_layout/orders.tsx`, `routes/_layout/orders.$orderId.receipt.tsx`, `components/Ordering/*`.
