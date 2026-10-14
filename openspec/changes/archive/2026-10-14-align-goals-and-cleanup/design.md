# Design

## Context

See proposal.md - Why. The prototype code is uncommitted (untracked or modified files in git), while the template's `Item` feature is committed and has an Alembic history (`e2412789c190_initialize_models.py` and later revisions create the `item` table).

## Goals / Non-Goals

**Goals:**
- A clean baseline containing only template auth/users/settings plus an empty dashboard.
- `goals.md` consistent with the chosen stack so later proposals do not re-litigate it.

**Non-Goals:**
- Introducing any OMS domain model (starts in `platform-foundation`).
- Changing authentication behavior.

## Decisions

- **Discard prototype files rather than port them.** They use `float` for money and lack ledger/idempotency; later changes redesign every table. Alternative considered: evolve them incrementally - rejected because almost every column and relationship changes.
- **Drop `Item` with a new migration, keep history.** Existing revisions stay untouched; a new revision drops `item`. Alternative: rewrite the initial migration - rejected because revisions may already be applied on dev databases.
- **goals.md edits are scoped.** Rewrite sections 1.2 (server-rendered principle), 2.2 (frontend), 2.6 (template reuse), 3.2 (structure), 3.4 (request flow), 11.3 (frontend interaction). Business requirements stay unchanged.

## Risks / Trade-offs

- [Prototype code may contain ideas worth keeping, such as Vietnamese labels like "Nguyên vật liệu"] → Capture useful labels/categories into later proposals' seed data before deleting.
- [Generated client drift] → Regenerate client and run `bun run build` as part of the change.
