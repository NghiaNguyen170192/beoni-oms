# Proposal

## Why

Shop owners can miss completed POS orders because the application has no durable, visible alert. An in-app notification center and corner popup will help signed-in owners notice and revisit orders that need attention.

## What Changes

- Create a persistent unread notification for each active owner when a POS order completes successfully.
- Add an owner-only notification center with read/unread state and links to the related order.
- Show a non-modal corner popup for newly detected unread notifications while an owner is signed in.
- Use in-app polling only; do not add browser, mobile, or background push delivery.

## Capabilities

### New Capabilities

- `notifications`: Persist and display actionable in-app notifications for completed POS orders.

### Modified Capabilities

None.

## Impact

- Backend: order completion, owner-only notification APIs, persistence, and an Alembic migration.
- Frontend: owner notification center, periodic unread refresh, corner popup, and navigation to order details.
- No external push provider, VAPID configuration, service worker, or separate worker deployment.
