# Design

## Context

Extends `ordering-pos`'s completion hook and status machine. `accounting-basic` will later project payments and refunds into cash/bank movements, so they must carry method kind and timestamps.

## Goals / Non-Goals

**Goals:** duplicate-safe money records with clear links to orders and lines.

**Non-Goals:** payment gateway / QR integrations, card terminals, tips, store credit, refunds on non-completed orders (void instead).

## Decisions

- **Tables:** `payment_methods` (name unique, kind check, active), `payments` (order_id, method_id, amount > 0, tendered, change, reference, status `active|voided`, void_reason, recorded_by, recorded_at), `refunds` (order_id, method_id, amount > 0, reason, recorded_by, recorded_at), `refund_lines` (refund_id, order_line_id, quantity, amount).
- **Paid amount is derived** (`sum(active payments) - 0`), not stored, avoiding drift; order row lock serializes concurrent payments on one order.
- **Pay-and-complete** = one service call: lock order → record payment → `complete_order` steps (which already include `ensure_paid`) → single commit. One idempotency key covers the combined operation (scope `order.pay_complete`).
- **Refund cap** uses paid amount, not order total, so a fully paid order cannot be refunded more than received.
- **Bank transfers are manually recorded** with reference text; no reconciliation status in v1 (goals.md 7.5).
- **Permissions:** cashier gets `payments:record`, `payments:view` (own); manager adds `payments:void`, `payments:refund`; owner `payments:configure`; accountant `payments:view`.

## Risks / Trade-offs

- [Cashier forgets to complete after paying] → POS default action is pay-and-complete; paid-but-not-completed orders are listed in POS as "awaiting completion".
