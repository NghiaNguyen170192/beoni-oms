# Spec Delta

## MODIFIED Requirements

### Requirement: Sales are recognized once at completion
Gross product sales, discounts, VAT-inclusive fee charges, and taxes SHALL be recognized on the order's completion date for orders that reached completed status; VAT extracted from fees SHALL be included in taxes. Draft, confirmed, paid-but-not-completed, and cancelled orders SHALL be excluded. Payments SHALL NOT be counted as revenue.

#### Scenario: Paid but not completed
- **WHEN** an order is paid but not completed in the period
- **THEN** it does not contribute to sales or fee revenue

#### Scenario: Completed order with a fee
- **WHEN** an order with product sales and a VAT-inclusive fee is completed in the period
- **THEN** its product sales and gross fee charge are recognized separately in that period, and the fee's embedded VAT is included in taxes

### Requirement: Profit formulas
For a period, net sales SHALL equal gross product sales plus gross VAT-inclusive fee charges minus discounts, refunds, and taxes collected; taxes collected SHALL include VAT extracted from fees. COGS SHALL equal sale-consumption cost minus sellable-return cost; gross profit SHALL equal net sales minus COGS; operating profit SHALL equal gross profit minus non-reversed expenses dated in the period.

#### Scenario: Example period
- **WHEN** a period has gross product sales of 1,000,000, VAT-inclusive fees of 20,000 (including 1,818 VAT), discounts of 50,000, refunds of 30,000, total tax of 1,818, COGS of 400,000, and expenses of 200,000
- **THEN** net sales are 938,182, gross profit is 538,182, and operating profit is 338,182

#### Scenario: Fees do not affect product cost
- **WHEN** a completed order has a fee in addition to product lines
- **THEN** the fee is not attributed to product sales, product categories, or COGS

### Requirement: Income listing
Users with finance view permission SHALL list completed orders in a period with order reference, completion date, gross product sales, discounts, VAT-inclusive fees, refunds, taxes (including VAT extracted from fees), net sales, and payment status.

#### Scenario: Income row
- **WHEN** an accountant views income for today
- **THEN** each completed order appears once with VAT-inclusive fees shown separately from gross product sales and included in net sales, and the embedded fee VAT included in taxes
