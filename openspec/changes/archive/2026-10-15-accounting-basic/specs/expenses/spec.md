# Spec Delta

## Purpose

Records the business's operating expenses by category so that operating profit can be estimated and spending reviewed.

## ADDED Requirements

### Requirement: Record expenses
Users with expense permission SHALL record an expense with category, amount greater than zero, expense date, description, payment status (paid or unpaid), payment account when paid, and the responsible user.

#### Scenario: Pay rent
- **WHEN** an accountant records rent of 10,000,000 VND paid from Bank
- **THEN** the expense is saved and a bank outflow of 10,000,000 VND is recorded

#### Scenario: Missing account for paid expense
- **WHEN** a paid expense is submitted without a payment account
- **THEN** the system rejects it

### Requirement: Expense categories
Owners SHALL manage expense categories; the defaults rent, utilities, salaries, equipment, maintenance, marketing, delivery, and other SHALL exist. Categories in use SHALL only be deactivated.

#### Scenario: Add category
- **WHEN** an owner adds category "Packaging supplies"
- **THEN** it is selectable for new expenses

### Requirement: Paying an unpaid expense
An unpaid expense SHALL be markable as paid with an account and payment date, which records the corresponding money outflow.

#### Scenario: Pay electricity later
- **WHEN** an unpaid utilities expense is marked paid from Cash drawer
- **THEN** a cash outflow dated on the payment date is recorded

### Requirement: Expenses are corrected by reversal
Recorded expenses SHALL NOT be edited in amount, date, or category or deleted; a reversal with reason SHALL cancel the expense and any money outflow by an opposite movement.

#### Scenario: Reverse wrong amount
- **WHEN** an accountant reverses an expense recorded with the wrong amount
- **THEN** the expense is marked reversed, an opposite money movement is recorded, and a new expense can be entered

### Requirement: Expense recording is idempotent
Recording, paying, and reversing expenses SHALL require an idempotency key and SHALL NOT duplicate on retry.

#### Scenario: Double submit
- **WHEN** the same expense is submitted twice with the same key
- **THEN** one expense exists

### Requirement: Expense list
Users with expense view permission SHALL list expenses filtered by date range, category, payment status, and reversed flag, with totals by category.

#### Scenario: Monthly utilities
- **WHEN** a user filters this month's utilities
- **THEN** only matching non-reversed expenses and their total are shown
