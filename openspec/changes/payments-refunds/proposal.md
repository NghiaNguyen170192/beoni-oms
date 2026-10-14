# Proposal

## Why

An order is not a sale until money is recorded (goals.md section 5.6). Payments and refunds must be duplicate-safe, linked to their orders, and kept separate from revenue so accounting and reports reconcile.

## What Changes

- Add configurable payment methods (seeded: cash, bank transfer), each marked active or inactive.
- Record one or more payments per order with amount, method, reference, status, timestamp, and user; cash payments may record tendered amount and change.
- Add a single "pay and complete" operation for the common counter sale.
- Require recorded payments to cover the order total before completion; move orders to `paid` when fully paid.
- Allow voiding a payment on an order that is not yet completed.
- Add full and partial refunds linked to the original completed order (and optionally to lines), with reason, method, and actor; order status becomes partially_refunded or refunded.
- Refunds never change stock; returning goods to stock is a separate, explicit operation (delivered by `recipes-auto-deduction`).
- Add a Payments and Refunds page and payment/refund panels in POS and order detail.

## Capabilities

### New Capabilities

- `payments`: payment methods, payment recording, payment-driven order states, voids, and refunds.

### Modified Capabilities

None.

## Impact

- Backend: new `backend/app/modules/payments/`, migration for `payment_methods`, `payments`, `refunds`, `refund_lines`; completion hook step `ensure_paid` in `ordering`; permissions `payments:record`, `payments:void`, `payments:refund`, `payments:view`, `payments:configure`.
- Frontend: payment dialog in POS, refund dialog in order detail, `routes/_layout/payments.tsx`, payment method management under Settings.
- Requires `ordering-pos`.
