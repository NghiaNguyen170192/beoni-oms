# Tasks

## 1. Align income rows with refund periods

- [x] 1.1 Update income listing to include only selected-period refunds on sale rows and add refund rows for earlier sales; add `kind` to the income schema and verify sale-day, refund-day, and combined-period net sales match `financial_summary`, including tax-exclusive refund net sales.

## 2. Expose refund rows in reports

- [x] 2.1 Add row kind to the income CSV, regenerate the OpenAPI client, and label refund rows in the income table; verify frontend lint/build and Playwright coverage for a refund row and CSV output.

## 3. Verify the integrated change

- [x] 3.1 Run focused accounting/report backend tests, relevant frontend tests and Playwright specs, frontend lint/build, and `openspec validate align-refund-income-periods`; resolve regressions and confirm all checks pass.
