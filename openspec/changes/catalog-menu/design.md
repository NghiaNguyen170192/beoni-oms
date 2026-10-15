# Design

## Context

Uses `require_permission`, `audit.record`, and module layout from `platform-foundation`. No inventory or recipe tables exist yet.

## Goals / Non-Goals

**Goals:** a stable `menu_items` table that orders and recipes reference by id.

**Non-Goals:** modifiers/toppings, combo items, time-based pricing, multiple price lists, tax configuration per item (tax rate is handled at order level in `ordering-pos`).

## Decisions

- **Permissions:** `catalog:view` (all roles that sell or report), `catalog:manage` (owner, manager).
- **Product type is a column, not subclasses.** Consumption behavior per type is implemented later by `recipes-auto-deduction`; changing the type of an item that has sales is allowed but audited.
- **"Has been sold" check** uses existence of an order line referencing the item; until `ordering-pos` lands, every item is deletable. Implemented as a service guard plus `ON DELETE RESTRICT` on the order line FK added later.
- **Images** stored on a backend media volume (`/app/media/menu/<uuid>.<ext>`), served via a static route; the item stores the relative path. Alternative: object storage - rejected for v1 simplicity.
- **Product codes** come from PostgreSQL sequence `menu_item_code_seq`, formatted `MENU-{n:05d}` in the service at create time; the code is absent from create/update payloads. A sequence (not `max()+1`) avoids races; gaps from rolled-back inserts are accepted. Order lines keep their snapshot of the code.
- **Seed data:** default categories "Cà phê", "Trà", "Đồ ăn", "Khác" on first migration (carried over from the prototype's "Đồ ăn" default). The prototype's sale-movement label "Bán hàng" maps to the `sale_consumption` movement type display name.

## Risks / Trade-offs

- [Local media volume not backed up] → `hardening-deployment` includes the media directory in backups.
