# Tasks

## 1. Persistent owner notifications

- [x] 1.1 Add the notification model with owner/order uniqueness and required foreign keys/indexes, plus an Alembic migration; verify migration upgrade/downgrade and constraints with backend tests.
- [x] 1.2 Create one unread notification per active owner inside successful order completion; verify completion rollback, replay/idempotency, and duplicate-prevention with backend tests.
- [x] 1.3 Add owner-only APIs for paginated notification history, unread count, and read/unread state; verify owner/superuser access, non-owner denial, and per-owner data isolation with backend tests.

## 2. In-app notification experience

- [x] 2.1 Regenerate the OpenAPI client and add the owner notification center with unread count and read/unread actions; verify frontend lint/build and Playwright coverage for the center.
- [x] 2.2 Refresh unread notifications every 15 seconds while an owner is signed in and show newly detected notifications as non-modal corner toasts; verify toast display, dismissal preserving unread state, and polling behavior with Playwright.
- [x] 2.3 Make order details addressable from the authenticated orders route and navigate there when an owner opens a notification; verify the correct order opens and access checks remain enforced with Playwright.
