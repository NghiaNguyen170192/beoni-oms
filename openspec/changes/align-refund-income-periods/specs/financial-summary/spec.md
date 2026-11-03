# Spec Delta

## MODIFIED Requirements

### Requirement: Income listing
Users with finance view permission SHALL list income rows for the selected period with order reference, row kind (`sale` or `refund`), order completion date, gross sales, discounts, fees, refunds, taxes, net sales, and payment status. Sale rows SHALL appear once per completed order in the period and include only refunds recorded in the selected period. Refunds recorded in the period against earlier completed orders SHALL appear as refund rows with zero gross sales, discounts, fees, and tax, and negative net sales equal to the refund amount excluding embedded tax. The reported refund amount SHALL be the amount returned to the customer. Payment status SHALL be paid, partially_refunded, or refunded based on all refunds against the order total.

#### Scenario: Income row
- **WHEN** an accountant views income for today
- **THEN** each completed order appears once with its net sales

#### Scenario: Refund recorded after the sale
- **WHEN** an order is completed on day 1 and refunded on day 2
- **THEN** day 1 lists the sale without the day 2 refund, and day 2 lists a refund row with zero sales and a negative tax-exclusive net sales amount

#### Scenario: Income listing reconciles across sale and refund periods
- **WHEN** an accountant views the income listing and financial summary for day 1, day 2, and both days together
- **THEN** the income listing's net sales total equals the financial summary's net sales for each period
