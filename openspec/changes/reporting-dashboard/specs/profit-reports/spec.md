# Spec Delta

## Purpose

Shows expenses by category and estimated profit for a period, compared with another period, using the financial summary rules.

## ADDED Requirements

### Requirement: Expense breakdown
The profit report SHALL list non-reversed expenses by category with amounts and share of total expenses for the period.

#### Scenario: Category totals
- **WHEN** a period has rent 10,000,000 and utilities 2,000,000
- **THEN** rent shows 83.3% and utilities 16.7% of expenses

### Requirement: Profit statement
The profit report SHALL show net sales, COGS, gross profit, gross margin percentage, expenses, and estimated operating profit, labelled as management estimates rather than statutory accounts.

#### Scenario: Labelled estimate
- **WHEN** a user opens the profit report
- **THEN** figures are shown with a note that they are estimates

### Requirement: Period comparison
Users SHALL compare the selected period with a previous period of equal length or a chosen period, showing both values and absolute and percentage change per line.

#### Scenario: Month over month
- **WHEN** a user compares this month with last month
- **THEN** each line shows both values and the change

### Requirement: Cost limitation notice
The profit report SHALL warn when the period contains cost-uncertain or missing-cost sales and show their count.

#### Scenario: Warning
- **WHEN** the period includes sales made with negative stock
- **THEN** a warning with the affected line count is displayed

### Requirement: Financial report access
Profit reports SHALL require financial report permission.

#### Scenario: Inventory staff denied
- **WHEN** inventory staff request the profit report
- **THEN** the system responds with 403
