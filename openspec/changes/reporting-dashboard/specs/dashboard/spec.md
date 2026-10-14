# Spec Delta

## Purpose

Gives owners and managers an immediate view of sales, costs, profit, and stock alerts for a chosen period.

## ADDED Requirements

### Requirement: Dashboard metrics
The dashboard SHALL show, for the selected period, net sales, completed order count, average order value (net sales divided by completed orders), discounts, refunds, COGS, gross profit, recorded expenses, estimated operating profit, and the current number of low-stock items.

#### Scenario: Today by default
- **WHEN** a manager opens the dashboard
- **THEN** metrics for today in the business timezone are shown

#### Scenario: No sales
- **WHEN** the period has no completed orders
- **THEN** average order value shows 0 and no error occurs

### Requirement: Dashboard date range filter
Users SHALL select a custom date range or presets (today, yesterday, last 7 days, this month, last month), and all metrics SHALL use the same boundaries.

#### Scenario: This month
- **WHEN** a user selects this month
- **THEN** every metric covers the first day of the month through today

### Requirement: Dashboard agrees with financial summary
Dashboard sales, COGS, expense, and profit figures SHALL equal the financial summary for the same period.

#### Scenario: Consistency
- **WHEN** the dashboard and the profit report are opened for the same period
- **THEN** their net sales, COGS, and profit values are identical

### Requirement: Role-appropriate dashboard
Users without financial report permission SHALL see sales and stock metrics only; cost and profit figures SHALL be hidden and not returned by the API.

#### Scenario: Manager without financial access
- **WHEN** a manager, who has sales report access but not financial report access, opens the dashboard
- **THEN** COGS and profit are not returned
