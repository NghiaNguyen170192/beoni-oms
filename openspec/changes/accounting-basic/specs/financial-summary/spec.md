# Spec Delta

## Purpose

Computes the period's income, cost of goods sold, and estimated profit from source transactions with one consistent set of rules shared by the dashboard and reports.

## ADDED Requirements

### Requirement: Sales are recognized once at completion
Gross sales, discounts, and taxes SHALL be recognized on the order's completion date for orders that reached completed status; draft, confirmed, paid-but-not-completed, and cancelled orders SHALL be excluded. Payments SHALL NOT be counted as revenue.

#### Scenario: Paid but not completed
- **WHEN** an order is paid but not completed in the period
- **THEN** it does not contribute to sales

### Requirement: Refunds reduce sales when recorded
Refunds SHALL reduce net sales in the period in which the refund was recorded.

#### Scenario: Refund next day
- **WHEN** an order completed on day 1 is refunded 29000 on day 2
- **THEN** day 1 net sales are unaffected and day 2 net sales are reduced by 29000

### Requirement: Profit formulas
For a period, net sales SHALL equal gross sales minus discounts minus refunds, excluding taxes collected; COGS SHALL equal sale-consumption cost minus sellable-return cost; gross profit SHALL equal net sales minus COGS; operating profit SHALL equal gross profit minus non-reversed expenses dated in the period.

#### Scenario: Example period
- **WHEN** gross sales are 1,000,000, discounts 50,000, refunds 30,000, tax 0, COGS 400,000, expenses 200,000
- **THEN** net sales are 920,000, gross profit 520,000, operating profit 320,000

### Requirement: Cost limitations are disclosed
The summary SHALL report counts of lines with uncertain or missing cost in the period.

#### Scenario: Negative stock sale
- **WHEN** a period includes a cost-uncertain line
- **THEN** the summary indicates one line with uncertain cost

### Requirement: Income listing
Users with finance view permission SHALL list completed orders in a period with order reference, completion date, gross sales, discounts, refunds, taxes, net sales, and payment status.

#### Scenario: Income row
- **WHEN** an accountant views income for today
- **THEN** each completed order appears once with its net sales

### Requirement: Dates use the business timezone
All period boundaries SHALL be whole days in the business timezone, inclusive of the start date and end date.

#### Scenario: Late-night sale
- **WHEN** an order completes at 23:30 Asia/Ho_Chi_Minh on 14 October
- **THEN** it belongs to 14 October even though it is 16:30 UTC
