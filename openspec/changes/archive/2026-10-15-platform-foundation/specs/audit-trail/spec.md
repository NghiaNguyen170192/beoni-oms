# Spec Delta

## Purpose

Provides an append-only, queryable history of who changed what and when for orders, payments, stock, recipes, prices, expenses, settings, and permissions.

## ADDED Requirements

### Requirement: Audit entries record actor, time, entity, and action
Each audit entry SHALL include the acting user, a UTC timestamp, entity type, entity identifier, action name, and a description or structured diff of the change.

#### Scenario: Role change is audited
- **WHEN** an owner changes a user's role from cashier to manager
- **THEN** an audit entry exists with the owner as actor, entity type user, action role_changed, and the old and new roles

### Requirement: Audit entries are written atomically with the change
An audit entry SHALL be committed in the same transaction as the business change it describes; if the change fails, no audit entry remains.

#### Scenario: Failed change leaves no audit entry
- **WHEN** a business operation fails and is rolled back
- **THEN** no audit entry for that operation exists

### Requirement: Audit log is append-only
The system SHALL NOT provide any API to update or delete audit entries.

#### Scenario: No mutation endpoints
- **WHEN** any client attempts to modify or delete an audit entry through the API
- **THEN** no such operation exists and the entry is unchanged

### Requirement: Owners can search the audit log
Owners SHALL be able to list audit entries filtered by entity type, entity identifier, actor, and date range, newest first and paginated.

#### Scenario: Filter by entity
- **WHEN** an owner filters the audit log by a specific order identifier
- **THEN** only entries for that order are returned in reverse chronological order

#### Scenario: Non-owner denied
- **WHEN** a cashier requests the audit log
- **THEN** the system responds with 403
