# Spec Delta

## Purpose

Explains sales performance over time, by payment method, and by product, using the same inclusion rules as the financial summary.

## ADDED Requirements

### Requirement: Sales summary
The sales summary SHALL report gross sales, discounts, refunds, net sales, order count, and average order value for the selected period, grouped by day, week, or month in the business timezone.

#### Scenario: Weekly grouping
- **WHEN** a manager groups the last 8 weeks by week
- **THEN** one row per week appears and the rows sum to the period totals

### Requirement: Payment method breakdown
The sales summary SHALL include amounts received per payment method net of refunds paid by that method, reported separately from sales revenue.

#### Scenario: Cash and bank
- **WHEN** a period has 600,000 cash and 400,000 bank payments and a 50,000 cash refund
- **THEN** the breakdown shows cash 550,000 and bank 400,000

### Requirement: Sales filters
Sales reports SHALL filter by date range, cashier, payment method, menu category, and order status, and SHALL exclude draft and cancelled orders from completed sales.

#### Scenario: Cancelled excluded
- **WHEN** a period contains a cancelled order
- **THEN** it is not included in completed sales totals

### Requirement: Product performance
Product performance SHALL list, per menu item, quantity sold, gross sales, discounts, net sales, estimated cost, estimated gross profit, and share of total net sales, sortable, with best and least sellers identified.

#### Scenario: Best seller
- **WHEN** a manager sorts by quantity sold
- **THEN** the item with the highest quantity appears first and is marked best seller

### Requirement: Product names from snapshots
Product reports SHALL group by menu item and display names from order line snapshots for the period, so renamed items still reconcile.

#### Scenario: Renamed item
- **WHEN** an item was renamed mid-period
- **THEN** its sales appear as one product row with the current name and include sales under the old name

### Requirement: Sales reports reconcile
Product performance net sales and quantities SHALL sum to the sales summary totals for the same filters.

#### Scenario: Totals match
- **WHEN** both reports are run for the same period
- **THEN** product net sales sum equals summary net sales
