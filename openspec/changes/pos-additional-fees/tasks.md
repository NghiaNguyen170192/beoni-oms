# Tasks

## 1. Persist fee configuration and order snapshots

- [x] 1.1 Add fee-type and order-fee models, the order fee-total field, uniqueness/foreign-key/check constraints, and one Alembic migration that preserves existing order totals; verify migration upgrade/downgrade and backend persistence/integrity tests.
- [x] 1.2 Update backend order pricing and serialization to derive totals as subtotal minus discounts plus VAT-inclusive fees, extracting embedded VAT with the order's saved rate while retaining fee name/amount snapshots; verify tax rounding, unchanged amount due, zero-fee omission, and existing-order compatibility tests.

## 2. Manage fees and shop name under Admin

- [x] 2.1 Add owner/superuser-only, audited APIs for fee-type creation, listing, rename, enable/disable, and dedicated shop-name updates; verify backend authorization, audit, rename, and disable-with-existing-order tests, and confirm the migration from 1.1 supports these endpoints.
- [x] 2.2 Regenerate the OpenAPI client, add the Admin fee and shop-name controls, and remove the shop-name editor from Settings → Business; verify frontend lint/build and Playwright coverage for owner access, non-owner denial, and saved settings.
- [x] 2.3 Expose the existing global VAT-rate setting under Admin and remove its editor from Settings → Business, reusing existing validation, authorization, and audit behavior; verify owner/superuser access, non-owner denial, validation, audit, and that rate changes affect new orders without changing existing order snapshots.

## 3. Apply and display order fees

- [x] 3.1 Add the open-order fee update workflow with backend validation, order locking, disabled-fee retention/removal rules, and immutable completed orders; verify backend tests for invalid amounts, disabled and unknown types, concurrent-safe total updates, and payment/completion totals.
- [x] 3.2 Update POS/order/receipt coverage as needed to verify fee snapshots remain separate, the amount due is unchanged by VAT extraction, and displayed order tax includes fee VAT; verify frontend lint/build and relevant Playwright coverage.

## 4. Report fee revenue separately

- [x] 4.1 Update financial-summary and income calculations/schemas to show VAT-inclusive fee charges separately from product sales, include extracted fee VAT in taxes, and retain the existing net-sales formula while leaving product/category sales and COGS unchanged; verify backend tests for tax extraction, completion-date recognition, discounts, refunds, taxes, and fee-excluded product costs.
- [x] 4.2 Regenerate affected client types and update financial-summary/income views to display the separate fee amount; verify frontend lint/build and Playwright assertions for fee revenue and unchanged product/category reporting.

## 5. Verify the integrated change

- [ ] 5.1 Run the focused backend tests, relevant frontend tests and Playwright specs, frontend lint/build, and `openspec validate pos-additional-fees`; resolve regressions and confirm all checks pass.
