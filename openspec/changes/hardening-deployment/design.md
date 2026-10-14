# Design

## Context

The template already ships Traefik with Let's Encrypt (`compose.traefik.yml`), a production `compose.yml`, Sentry wiring, and a `check_default_secret` warning in `app/core/config.py`. All business modules exist after `reporting-dashboard`.

## Goals / Non-Goals

**Goals:** recoverable single-host deployment; automated proof that cross-module invariants hold.

**Non-Goals:** high availability, replicas, point-in-time recovery, Kubernetes, off-site backup automation beyond a documented copy step.

## Decisions

- **Backups:** a `backup` Compose service (postgres image + cron loop) running `pg_dump -Fc` and `tar` of the media volume into a `backups` volume/bind mount, with retention pruning. Alternative: WAL archiving/PITR - rejected as overkill for v1. Off-site copy documented (rclone or manual) in `deployment.md`.
- **Restore script** `scripts/restore.sh <dump> <media.tar>`: stop backend, `pg_restore --clean --if-exists`, unpack media, run `alembic upgrade head`, start backend, call the integrity check.
- **Integrity check** implemented as SQL comparisons per invariant, returned as a structured report; also run in CI against the seeded e2e database.
- **Config guard:** turn the template's production warning for default secrets into a startup error.
- **Security headers** via a small middleware (backend) and Traefik headers middleware (frontend).
- **Route-access test** iterates `app.routes`, asserting each has a `require_permission` dependency or is in an explicit `PUBLIC_ROUTES` set (login, password recovery, health).
- **Load test:** k6 script in `loadtest/` simulating cashiers (create order, add lines, pay-and-complete), back office reads, and dashboard polls; targets from goals.md 12.1 on a single 2 vCPU / 4 GB host.

## Risks / Trade-offs

- [Backups on the same host as the database] → Documented off-site copy step and restore drill checklist.
- [Load test environment differs from production] → Record hardware and dataset size with results.
