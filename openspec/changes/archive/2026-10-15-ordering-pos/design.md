# Design

## Context

Depends on `catalog-menu` for menu items and `platform-foundation` for permissions, idempotency, audit, and settings (timezone, business name). Later, `payments-refunds` and `recipes-auto-deduction` extend the completion path.

## Goals / Non-Goals

**Goals:** a single `ordering.service` that owns order math and transitions, and a completion entry point that later changes can extend with payment and stock steps inside the same transaction.

**Non-Goals:** table/floor maps, kitchen display, split bills, customer loyalty, delivery integrations, offline POS.

## Decisions

- **Tables:** `orders` (number unique, type, table_label, status check, subtotal, discount_total, tax_total, total, order-level discount fields, cashier_id, confirmed_at, completed_at, completed_by, cancelled_at, cancel_reason), `order_lines` (menu_item_id RESTRICT, item_name, unit_price, quantity Numeric(18,3), discount_type/value/amount, tax_rate, tax_amount, line_total, discount_by).
- **Pure pricing module** `ordering/pricing.py` with Decimal math and `ROUND_HALF_UP` to whole VND; unit tested in isolation. Order discount is allocated to lines proportionally (last line takes remainder) so product reports have per-line net amounts.
- **State machine** as a transition table `ALLOWED: dict[Status, set[Status]]` with `assert_transition`. Order row is locked `FOR UPDATE` for every mutation.
- **Completion hook:** `complete_order` runs registered steps in order (`validate`, later `payments.ensure_paid`, `stock.consume`) within one transaction. Steps are plain function calls added by later changes, not a plugin framework.
- **Tax:** single tax rate from business settings, added as a setting `tax_rate` (default 0) in this change; tax-inclusive prices so totals match menu prices.
- **Order number:** `HD-YYYYMMDD-####` by business-timezone day, via a per-day counter row locked on insert.
- **Receipt:** frontend route rendering print CSS from the order API; no server-side PDF.
- **POS performance:** menu loaded once and cached with React Query; line mutations return the full recalculated order so the cart always shows backend totals.

## Risks / Trade-offs

- [Per-line roundtrips slow on poor Wi-Fi] → Batch endpoint `PUT /orders/{id}/lines` replacing all lines in one call; POS debounces quantity changes.
- [Tax setting added here touches business-settings] → Additive field with default; covered by settings tests.
