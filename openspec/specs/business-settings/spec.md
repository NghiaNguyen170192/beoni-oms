# business-settings Specification

## Purpose

Holds business-wide configuration such as currency, timezone, and stock policy that other modules read to behave consistently.

## Requirements

### Requirement: Single business settings record
The system SHALL maintain one business settings record with business name, currency code, timezone, and allow-negative-stock flag. Defaults SHALL be currency VND, timezone Asia/Ho_Chi_Minh, and negative stock disallowed.

#### Scenario: Defaults on fresh install
- **WHEN** the application starts against an empty database
- **THEN** reading settings returns currency VND, timezone Asia/Ho_Chi_Minh, and allow_negative_stock false

### Requirement: Only owners change settings
Only users with the owner role SHALL update business settings; every change SHALL be recorded in the audit trail with previous and new values.

#### Scenario: Owner enables negative stock
- **WHEN** an owner sets allow_negative_stock to true
- **THEN** the setting is saved and an audit entry records the old value false and new value true

#### Scenario: Manager cannot change settings
- **WHEN** a manager attempts to update settings
- **THEN** the system responds with 403

### Requirement: Settings values are validated
The timezone SHALL be a valid IANA timezone name and the currency SHALL be a supported ISO 4217 code.

#### Scenario: Invalid timezone rejected
- **WHEN** an owner submits timezone "Mars/Olympus"
- **THEN** the system rejects the update with a validation error

### Requirement: All authenticated users can read settings
Any authenticated user SHALL be able to read currency and timezone so amounts and dates display consistently.

#### Scenario: Cashier reads settings
- **WHEN** a cashier requests business settings
- **THEN** the system returns currency and timezone

### Requirement: Business-wide interface language
The business settings SHALL include an interface language, English (`en`) or Vietnamese (`vi`), defaulting to English. Only owners SHALL change it, from a Language page under Admin; the change SHALL be audited. Every user SHALL see the whole interface (navigation, pages, forms, validation messages, notifications, labels for statuses and types, and receipts) in the business language. Business data such as item and category names SHALL NOT be translated.

#### Scenario: Owner switches to Vietnamese
- **WHEN** an owner selects Vietnamese on the Language page
- **THEN** an audit entry records the change from en to vi and every user's interface shows Vietnamese text after their next page load

#### Scenario: Unsupported language rejected
- **WHEN** an owner submits language "fr"
- **THEN** the system rejects the update with a validation error

#### Scenario: Manager cannot change language
- **WHEN** a manager attempts to change the language
- **THEN** the system responds with 403
