# Tasks

## 1. Payment methods

- [ ] 1.1 Add `payment_methods` model, migration seeding cash and bank transfer, service and owner-only routes; verify tests for add, deactivate, and inactive-method rejection

## 2. Payments

- [ ] 2.1 Add `payments` model and migration; implement idempotent record-payment with cash tender/change and overpayment rules, paid-status transitions, and void; verify service tests for every payment scenario
- [ ] 2.2 Add `ensure_paid` completion step and pay-and-complete operation; verify service tests for unpaid rejection, atomic pay-and-complete, and duplicate key
- [ ] 2.3 Add routes `/orders/{id}/payments`, `/payments/{id}/void`, `/orders/{id}/pay-and-complete` with `Idempotency-Key`; verify API tests including permissions

## 3. Refunds

- [ ] 3.1 Add `refunds` and `refund_lines` models and migration; implement idempotent refunds with cap and status transitions, no inventory movement; verify service tests for partial, full, over-refund, and no stock change
- [ ] 3.2 Add `/orders/{id}/refunds` routes and `/payments` + `/refunds` list endpoints with filters and per-method totals; verify API tests

## 4. Frontend

- [ ] 4.1 Regenerate client; add POS payment dialog (method buttons, cash tender keypad with change, split payments, pay-and-complete); verify build and lint
- [ ] 4.2 Add refund dialog in order detail with confirmation, payment method management in Settings, and Payments and Refunds page with filters and totals; verify build and lint
- [ ] 4.3 Add Playwright spec: cash sale with change, split payment, partial refund, full refund; verify spec passes

## 5. Integration check

- [ ] 5.1 Add an integration test confirming refunds leave all inventory balances unchanged and payment totals per method match the list endpoint
