# Design

## Context

POS saves editable draft orders and completes them through a separate idempotent operation in `ordering.service`. The application has no notification API or real-time event transport. See `proposal.md` and `specs/notifications/spec.md` for the motivation and behavior contract.

## Goals / Non-Goals

**Goals:**
- Keep owner notification history durable and atomic with successful order completion.
- Make new unread notifications visible in the signed-in owner interface without disrupting work.
- Restrict notification access to the existing owner role, including superusers.

**Non-Goals:**
- Browser, mobile, or background push delivery; notifications while the application is closed.
- Notifications for batches, stock adjustments, supplier receipts, or other events.
- A general-purpose event bus, configurable notification rules, or Supabase integration.

## Decisions

1. **Persist one notification per completed order and owner in the completion transaction.** Add a unique constraint on `(owner_id, order_id)` and create notifications only as part of successful order completion. This makes notifications atomic with the completed order and protects against duplicate completion retries.

2. **Use the existing owner role as the access boundary.** The project has no separate `administrator` role; it has `owner`, `manager`, `cashier`, `inventory_staff`, and `accountant`, and superusers are treated as owners. Only active owners/superusers receive and access these notifications. Adding a new role or granting managers access is out of scope.

3. **Poll the owner notification API while the app is active.** The signed-in owner layout refreshes unread notifications every 15 seconds and shows newly observed items as non-modal corner toasts. Polling reuses the existing API/session model and avoids adding Supabase, WebSockets, or a broker for a single notification type. Dismissal is only presentation state; opening the item marks it read. The persistent center remains the source of truth.

4. **Use the existing order details as the destination.** Add an order identifier to the orders route so the notification center and corner toast can navigate to the same order detail sheet. Existing authentication and owner role checks continue to apply.

5. **Keep the popup intentionally in-app.** Do not request browser notification permission or add a service worker, push subscription, VAPID key, external provider, outbox, or separate worker. If the owner is signed out or the app is closed, no popup is shown; the notification remains unread and is available on the next visit.

## Risks / Trade-offs

- [Polling may show a notification up to one interval late] -> Use a 15-second interval while the owner app is active; the center remains available for manual review.
- [Polling adds periodic requests] -> Poll only for authenticated owners and stop/refocus polling according to application lifecycle.
- [No notification is shown while the application is closed] -> Keep the alert unread and durable in the owner notification center.
- [There is no distinct administrator role] -> Use the established owner/superuser role mapping and do not silently broaden visibility to managers.

## Migration Plan

1. Apply the migration for persistent notifications; no push subscription or delivery tables are needed.
2. Deploy the backend and frontend. Owners will see unread notifications in the center and corner popups while signed in.

Rollback by reverting the application before removing the notification table. Do not drop notification data as part of routine rollback.
