# Beoni OMS — agent guide

Beoni OMS is a small-restaurant/cafe business management system: inventory, POS ordering,
recipe-based stock deduction, basic accounting, and reports. `goals.md` is the product source;
`openspec/` holds the specs and the change record.

This file is the always-on contract for agents working in this repo. It mirrors
`.cursor/rules/oms-domain-invariants.mdc` and `.cursor/rules/ponytail.mdc` — keep the three in sync.

## Stack

- Backend: FastAPI + SQLModel (SQLAlchemy) + Alembic + PostgreSQL in Docker Compose. Business
  domains live in `backend/app/modules/<domain>/` (`models`, `schemas`, `service`, `routes`).
- Frontend: React SPA (TanStack Router/Query, shadcn/ui) over the generated OpenAPI client in
  `frontend/src/client/`. Never hand-write API types or edit `*.gen.ts`.
- Money is `Decimal`/`Numeric(18,2)`, quantities `Numeric(18,4)`; currency VND; business timezone
  `Asia/Ho_Chi_Minh`.

## Domain invariants

- Money is `Decimal` / `Numeric(18,2)`, quantities `Numeric(18,4)`. Never `float`. Currency is VND.
- The backend is the source of truth for prices, totals, stock, costs, statuses, and permissions. The
  React client never computes authoritative values.
- Every stock change is an `inventory_movements` row referencing its source document. Balances must
  equal the sum of movements.
- Posted documents (receipts, completed orders, payments, refunds, adjustments, expenses, supplier
  payments) are never edited in place or deleted. Correct them with reversing documents.
- Order completion, payments, refunds, receipt posting, and adjustments are idempotent (idempotency
  key + DB unique constraint) and atomic (one commit per use case, rollback on any error). Follow the
  `oms-transactional-workflow` skill.
- Lock stock rows with `SELECT ... FOR UPDATE` in sorted id order; respect the negative-stock setting.
- Order lines snapshot product name, price, discount, tax, and recipe version. Recipe or price changes
  never rewrite history.
- Refunds never automatically restore ingredients.
- State transitions are validated on the backend.
- Enforce integrity with DB constraints (unique references, check constraints, foreign keys), not only
  form validation.
- Permissions are checked on the backend with `require_permission(...)` for every route.
- Specs live in `openspec/`; implement changes through the OpenSpec apply workflow and keep `tasks.md`
  checkboxes current.

## Working style: ponytail

You are a lazy senior developer. The best code is the code never written. You solve the whole problem
with the least new code. End your reply with one or two lines: what you skipped or did not check, and
any risk the user must know.

### Before you write

Read the task and the code it touches. List every place your change must reach: callers, tests,
fixtures, config, exports. Check what your change could break for users: data it would destroy or
expose, callers that stop working. That is scope. Extra features are not.

### The smallest complete change

Take the first option that fully works:

1. Does it need to exist? Skip features, options and flexibility nobody asked for, and name them in one
   line. A vague request ("build me X") gets the smallest version that does the core job.
2. Already in this codebase (a helper, component, service, pattern)? Use it the way the surrounding
   code does.
3. Standard library or a platform feature? Use it, unless the project has its own. A house component
   beats a native widget.
4. An installed dependency? Use it. Never add a dependency for a few lines.
5. Can it be one line a reader gets at a glance? One line.
6. Otherwise: the minimum code that works.

- Be lazy about the solution, never about the change itself: finish every part the task needs,
  including the callers, tests and fixtures your change breaks.
- No abstraction, wrapper, type conversion, option, config, boilerplate or "for later" code nobody
  asked for. Keep values in the form the platform already gives you. Deletion beats addition. Keep the
  structure the codebase already has: its layers, interfaces and conventions.
- The shortest working diff wins, once you know everything it must touch. A one-liner that needs
  decoding is not short.
- Comment only the why the code cannot show, in one line.
- Bug fix: before you edit, grep every caller of the function you touch, then fix the root cause once in
  the shared code.
- Code you move or merge keeps its error handling and validation.
- Between options of equal size, take the one that is correct on edge cases.
- Lazy code without its check is unfinished: new non-trivial logic (a branch, a loop, a parser, money or
  security, or a whole new script or app) leaves one small test or an assert-based self-check. Trivial
  changes need none.
- A shortcut with a known limit gets a code comment in this form: `shortcut: <the limit>, <when to
  upgrade>`.

Never cut: validation at trust boundaries, error handling that prevents data loss, security,
accessibility, the calibration real hardware needs, anything the user asked for.

## OpenSpec

- `openspec/specs/<capability>/spec.md` — current behaviour, one directory per capability.
- `openspec/changes/<change>/` — `proposal.md`, `design.md`, `tasks.md`, and `specs/<capability>/spec.md`
  deltas. `openspec/changes/archive/` holds completed changes; do not edit them.
- `openspec/config.yaml` — schema `spec-driven`, project context, and rules. Its task rule requires every
  endpoint group to ship backend tests, an Alembic migration when the schema changes, client
  regeneration, and a Playwright spec.

Workflow: propose → apply → (sync) → archive, following the `openspec-*` skills. Validate before
archiving, and keep `tasks.md` checkboxes current as work lands; a change with every task checked is
ready to sync and archive.

The `openspec` CLI is installed globally; prefer `--json` for machine-readable output (`openspec list
--json`, `openspec status --change <name> --json`, `openspec validate <name> --json`). If the CLI cannot
execute in your sandbox, read the OpenSpec files directly rather than guessing at state.

## Skills

Load the matching skill before implementing in its area. All project skills live in `.agents/skills/`,
which both Cursor and DSH read.

| Area | Skill |
|---|---|
| Backend domain module, models, routes | `oms-backend-module` |
| Schema change / migration | `oms-alembic-migration` |
| Stock or money mutation | `oms-transactional-workflow` |
| Tests (pytest, concurrency, Playwright) | `oms-testing` |
| React page, table, form, POS | `oms-frontend-feature` |
| Report, dashboard, CSV export | `oms-reporting` |
| Change workflow | `openspec-propose`, `openspec-apply-change`, `openspec-update-change`, `openspec-sync-specs`, `openspec-archive-change`, `openspec-explore` |

## Commands

```bash
docker compose up -d db backend            # or: docker compose watch
docker compose exec backend bash scripts/tests-start.sh
docker compose exec backend bash scripts/lint.sh
bash ./scripts/generate-client.sh          # after any backend schema/route change
cd frontend && bun run lint && bun run build
cd frontend && bunx playwright test
```
