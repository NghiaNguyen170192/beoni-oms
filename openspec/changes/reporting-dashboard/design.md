# Design

## Context

All source tables exist. `accounting.financial_summary` and the timezone period helper exist. Conventions are captured in the `oms-reporting` skill.

## Goals / Non-Goals

**Goals:** read-only SQL reports that reconcile by construction; one query per report shared by JSON and CSV.

**Non-Goals:** materialized views or warehouse tables, scheduled email reports, PDF export, custom report builder.

## Decisions

- **One function per report** returning typed row models; routes call it for JSON and `csv_stream(rows)` for export. Guarantees export == screen.
- **Dashboard composes** `financial_summary` plus counts; no separate math.
- **Opening stock** = sum of movements before period start; closing = opening + period movements. Works because the ledger is complete since `inventory-core`.
- **Product performance** groups by `menu_item_id`, display name = current item name (falls back to latest snapshot if item deleted); net per line uses allocated order discount from `ordering`.
- **Permission-filtered fields:** response schemas omit cost/profit fields unless `reports:financial`; separate schema classes, not runtime nulling.
- **Indexes** added in this change's migration based on report predicates; verify with `EXPLAIN ANALYZE` via the Postgres MCP on a seeded dataset (about 50k orders).
- **Charts:** shadcn chart components (recharts) for trend lines; tables remain the primary output.

## Risks / Trade-offs

- [Large ranges slow on bigger shops] → Index + date-range cap of 366 days per request; revisit with summary tables only if p95 targets are missed.
- [New frontend dependency (recharts)] → Justified by charts requirement; limited to the reports route chunk via lazy loading.
