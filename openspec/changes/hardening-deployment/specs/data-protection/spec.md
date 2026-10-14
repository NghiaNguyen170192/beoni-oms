# Spec Delta

## Purpose

Protects business data against loss and silent corruption through scheduled backups, a verified restore path, and an integrity check across stock and money records.

## ADDED Requirements

### Requirement: Scheduled backups
The deployment SHALL create a full database backup and a media files archive at least daily, retain at least 14 daily and 8 weekly backups, and store them outside the database volume.

#### Scenario: Daily backup created
- **WHEN** the scheduled backup time passes
- **THEN** a new timestamped database dump and media archive exist in the backup location

#### Scenario: Retention
- **WHEN** more than 14 daily backups exist
- **THEN** the oldest daily backups beyond retention are removed

### Requirement: Backup failure is visible
A failed backup SHALL be logged as an error and reported to the configured error tracker.

#### Scenario: Disk full
- **WHEN** a backup fails because the target is full
- **THEN** an error log entry and an error-tracker event are produced

### Requirement: Restore procedure
A documented restore command SHALL restore a chosen backup into an empty database and media directory, after which the application starts and the integrity check passes.

#### Scenario: Restore drill
- **WHEN** an operator restores yesterday's backup into a fresh environment
- **THEN** the application serves yesterday's data and the integrity check reports no issues

### Requirement: Integrity check
Owners SHALL run an integrity check reporting any item whose balance differs from its movement sum, any money account whose balance differs from its movements, any payable whose paid amount differs from its allocations, and any order whose totals differ from its lines.

#### Scenario: Clean data
- **WHEN** an owner runs the integrity check on consistent data
- **THEN** the result reports zero issues in every category

#### Scenario: Detected drift
- **WHEN** an item's stored balance differs from its movements
- **THEN** the check lists that item with stored and computed quantities

#### Scenario: Non-owner denied
- **WHEN** a manager runs the integrity check
- **THEN** the system responds with 403
