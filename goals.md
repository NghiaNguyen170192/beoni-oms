# GOALS.md — Simplified Business Management System

## 1. Project Overview

Build a simplified business management web application inspired by KiotViet for small restaurants, cafés, beverage shops, and food businesses.

The application centralizes five essential business functions:

1. Inventory management.
2. Ordering and point-of-sale (POS).
3. Recipe-based automatic inventory deduction.
4. Basic accounting.
5. Sales reports and business analytics.

The goal is to provide a lightweight, reliable, and maintainable alternative to a full-featured retail management platform.

The system should prioritize practical business workflows over excessive features or architectural complexity.

### 1.1 Target Users

- Small restaurant owners.
- Café and beverage shop owners.
- Food stall operators.
- Cashiers and sales staff.
- Inventory managers.
- Accountants and business administrators.

### 1.2 Core Principles

- **Simplicity first:** Implement essential features without unnecessary complexity.
- **API-first web application:** A FastAPI backend exposes a typed JSON API; a React single-page application consumes it through a generated OpenAPI client. The backend remains the source of truth for all business rules.
- **Fast development:** Reuse the full-stack-fastapi-template (FastAPI backend plus React frontend).
- **Inventory accuracy:** Every stock change must be traceable.
- **Automatic deduction:** Completed sales deduct the required ingredients or products automatically.
- **Financial consistency:** Sales, payments, expenses, and refunds must reconcile with their underlying transactions.
- **Maintainability:** Use a modular monolith instead of microservices.
- **Minimal dependencies:** Avoid unnecessary libraries, frontend frameworks, and infrastructure.
- **Extensibility:** Keep business modules separated enough to support future enhancements.

---

## 2. Technology Stack

### 2.1 Backend

- Python 3.12 or a compatible supported Python version.
- FastAPI.
- Pydantic for request validation and data schemas.
- SQLModel (built on SQLAlchemy) for database access and ORM, as provided by the template.
- Alembic for database migrations.
- Jinja2 only for email templates, as provided by the template.

### 2.2 Frontend

Use the template's React single-page application.

Technologies:

- React with TypeScript, built with Vite.
- TanStack Router for file-based routing.
- TanStack Query for server state and caching.
- shadcn/ui components on Tailwind CSS.
- react-hook-form and zod for forms.
- A client generated from the backend OpenAPI schema (`@hey-api/openapi-ts`); API types are never written by hand.
- Biome for linting and formatting; Playwright for end-to-end tests.

Avoid adding further frontend frameworks or state libraries unless a concrete requirement justifies it.

### 2.3 Database

Use PostgreSQL as the recommended production database.

The application should support relational transactions for operations involving:

- Order completion.
- Inventory deduction.
- Payment recording.
- Stock receiving.
- Refund processing.
- Accounting records.

SQLite may be used for local experimentation or lightweight automated tests, provided production-specific transaction and concurrency behavior is tested against PostgreSQL.

### 2.4 Testing

Use:

- pytest.
- HTTPX for FastAPI endpoint testing.
- SQLAlchemy-compatible test fixtures.
- PostgreSQL integration tests for transaction and concurrency-sensitive workflows.

### 2.5 Deployment

Prefer a simple deployment model:

- One FastAPI application.
- One PostgreSQL database.
- One reverse proxy when needed.
- Docker Compose for local development and straightforward self-hosting.
- Automated database backups.

Do not introduce Kubernetes, message brokers, or microservices for the initial release.

### 2.6 Template Reuse

The project is built on the official full-stack-fastapi-template rather than boilerplate written from scratch.

The template provides:

- FastAPI application initialization.
- Configuration through environment variables.
- SQLModel database sessions.
- Alembic migrations.
- A React frontend with a generated API client.
- JWT authentication and user management, extended with business roles.
- Structured logging.
- Automated testing.
- Docker-based development.

Reuse the template's existing conventions when they are appropriate.

Do not replace working template components simply to adopt a different library or coding style.

---

## 3. Application Architecture

### 3.1 Architectural Style

Use a **modular monolith**.

All business modules run within the same FastAPI application and use the same PostgreSQL database.

Keep domain logic separate from HTTP handlers, frontend components, and database persistence.

Avoid microservices, distributed transactions, and unnecessary abstraction layers.

### 3.2 Project Structure

The structure follows the full-stack-fastapi-template, with business domains added as modules:

```text
backend/
├── app/
│   ├── main.py
│   ├── core/                 # config, db, security (template)
│   ├── api/
│   │   ├── deps.py           # session, current user, permissions
│   │   ├── main.py           # router registration
│   │   └── routes/           # template routes (login, users, utils)
│   ├── modules/
│   │   └── <domain>/         # identity, catalog, inventory, purchasing, recipes,
│   │       ├── models.py     # ordering, payments, accounting, reporting
│   │       ├── schemas.py
│   │       ├── service.py
│   │       └── routes.py
│   ├── alembic/
│   └── email-templates/
└── tests/
    └── modules/<domain>/

frontend/
├── src/
│   ├── client/               # generated OpenAPI client (do not edit)
│   ├── routes/_layout/       # one file route per page
│   ├── components/<Domain>/  # page components, tables, dialogs
│   └── components/ui/        # shadcn/ui primitives
└── tests/                    # Playwright specs

compose.yml
.env
```

Each domain module owns its tables, schemas, services, and routes. Services contain the business rules and transaction boundaries; routes stay thin.

### 3.3 Module Responsibilities

| Module | Responsibility |
|---|---|
| Identity | Authentication, users, roles, and permissions. |
| Catalog | Menu items, products, categories, and prices. |
| Inventory | Inventory items, suppliers, stock receipts, adjustments, and movements. |
| Recipes | Recipe definitions, versions, and ingredient consumption calculations. |
| Ordering | Orders, order items, payments, cancellations, and refunds. |
| Accounting | Expenses, supplier payables, cash movements, and cost calculations. |
| Reporting | Sales summaries, product performance, inventory reports, and profit estimates. |

Modules may call each other's application services directly when needed. Keep dependencies explicit and avoid circular imports.

### 3.4 Request Processing

A typical request should follow this flow:

```text
React page (TanStack Query)
   |
   v
Generated API client (JSON over HTTPS, bearer token)
   |
   v
FastAPI Route
   |
   v
Authentication and Authorization
   |
   v
Application Service
   |
   v
SQLModel Session
   |
   v
PostgreSQL
   |
   v
Pydantic response schema
   |
   v
JSON Response rendered by React
```

Business rules must not live in route handlers or frontend components.

Use shared application services for critical workflows such as order completion, stock receiving, and refunds.

### 3.5 Database Session Management

- Use SQLAlchemy sessions with explicit lifecycle management.
- Ensure sessions are closed after requests.
- Keep database transactions within clearly defined service boundaries.
- Avoid committing independently inside every repository operation.
- Commit related business changes together.
- Roll back failed database transactions.
- Use appropriate locking or concurrency controls for stock-sensitive operations.

---

## 4. Goal 1 — Inventory Management

### 4.1 Objective

Manage ingredients, merchandise, packaging, purchases, stock levels, and inventory movements.

### 4.2 Inventory Items

Each inventory item should support:

- SKU or unique item code.
- Name and description.
- Category.
- Item type.
- Base unit.
- Purchase unit.
- Unit conversion factor.
- Current quantity.
- Minimum stock threshold.
- Inventory cost.
- Active or inactive status.
- Optional barcode.
- Creation and modification timestamps.

Supported types:

- Ingredients.
- Direct-sale merchandise.
- Packaging materials.
- Other consumables.

Examples include coffee beans, milk, sugar, takeaway cups, and bottled water.

### 4.3 Unit Conversion

Support simple, configurable conversions between purchase units and base units.

Example:

- Purchase 5 kilograms of coffee beans.
- Store 5,000 grams.
- Deduct 18 grams per coffee sold.

Requirements:

- Every inventory item has a defined base unit.
- Purchase quantities are converted before posting.
- Recipes use the inventory item's base unit.
- Invalid conversion factors are rejected.
- Historical movements preserve their original quantities and costs.

### 4.4 Supplier Management

Users must be able to:

- Create and edit suppliers.
- Store supplier contact details.
- Record supplier purchases.
- Review purchase history.
- Track amounts paid.
- Track outstanding balances.
- Record purchase reference numbers and dates.

### 4.5 Stock Receiving

A purchase receipt must include:

- Receipt reference.
- Supplier.
- Receipt date.
- Inventory items and quantities.
- Unit costs.
- Total value.
- Payment status.
- Notes.
- Responsible user.

When a receipt is posted, the system must:

1. Validate the receipt.
2. Convert purchase quantities into base units.
3. Increase inventory.
4. Record inventory movements.
5. Update inventory valuation.
6. Record the relevant supplier payable.
7. Record any associated payment.
8. Make the transaction available to reports.

Draft receipts must not affect inventory.

Posted receipts must be corrected through explicit reversal or adjustment workflows rather than silent historical edits.

### 4.6 Stock Adjustments

Authorized users must be able to adjust stock for:

- Physical counts.
- Spoilage.
- Expired ingredients.
- Damaged goods.
- Missing stock.
- Data corrections.

Each adjustment must record:

- Inventory item.
- Previous quantity.
- Adjustment amount.
- Resulting quantity.
- Reason.
- Timestamp.
- Responsible user.

Adjustments must create inventory movements and update inventory valuation when appropriate.

### 4.7 Inventory Reports

Provide:

- Current stock levels.
- Low-stock items.
- Negative-stock items.
- Stock movement history.
- Stock received.
- Stock consumed.
- Stock adjustments.
- Inventory valuation.

### 4.8 Acceptance Criteria

- Posted receipts increase stock correctly.
- Stock adjustments produce traceable movements.
- Draft transactions do not affect stock.
- Posted transactions cannot be silently deleted.
- Concurrent stock updates cannot silently overwrite each other.
- Low-stock items can be identified quickly.

---

## 5. Goal 2 — Menu and Ordering Service

### 5.1 Objective

Provide a simple point-of-sale interface for creating orders, managing order items, collecting payments, and completing sales.

The interface should be optimized for fast operation on desktop and tablet screens.

### 5.2 Menu Management

Each menu item should support:

- Product code.
- Name.
- Description.
- Category.
- Selling price.
- Optional image.
- Active or inactive status.
- Optional availability settings.
- Recipe mapping, where applicable.

Support three product types:

1. Prepared items that consume ingredients.
2. Direct-sale products that deduct their corresponding inventory.
3. Non-stock items that do not affect inventory.

### 5.3 Order Creation

Users must be able to:

- Create an order.
- Add products.
- Change quantities.
- Remove items.
- Apply authorized discounts.
- Add notes.
- Review totals.
- Save drafts.
- Cancel eligible orders.
- Record payments.
- Print or export receipts.

The initial release should support:

- Counter sales.
- Takeaway.
- Basic dine-in orders.

Advanced table management is out of scope.

### 5.4 Order Lifecycle

Use a clearly defined order state machine.

Recommended states:

- Draft.
- Confirmed.
- Paid.
- Completed.
- Cancelled.
- Partially refunded.
- Refunded.

Not every transition needs to be a separate user action.

For example, a cash sale may be paid and completed through one operation.

The backend must validate all state transitions. A frontend button must never be the only protection against invalid transitions.

### 5.5 Order Price Snapshots

Each order item must preserve the relevant historical information:

- Product identifier.
- Product name at the time of sale.
- Unit selling price.
- Quantity.
- Discount.
- Applicable tax.
- Line total.
- Relevant recipe or inventory-consumption reference.

Changing a product's name, price, or recipe must not rewrite completed historical sales.

### 5.6 Payment Management

Support:

- Cash.
- Manually recorded bank transfers.
- Configurable payment methods.
- Multiple payments per order when needed.
- Full refunds.
- Partial refunds.
- Payment references.

Payment records must include amount, method, status, timestamp, and the associated order.

Prevent duplicate payment recording and repeated processing of the same refund operation.

### 5.7 Acceptance Criteria

- The backend calculates all order totals.
- Invalid quantities and discounts are rejected.
- Draft orders do not deduct stock.
- Completed sales cannot be processed twice.
- Cancelled drafts do not contribute to revenue.
- Refunds remain linked to the original sale.
- Historical orders preserve their original prices and item details.

---

## 6. Goal 3 — Recipes and Automatic Inventory Deduction

### 6.1 Objective

Automatically deduct ingredients or products when a sale is finalized.

This module connects the ordering service to inventory management.

### 6.2 Recipe Management

A recipe must define:

- Menu item.
- Recipe version.
- Ingredients.
- Required quantities.
- Base units.
- Effective date.
- Active status.

Example:

| Ingredient | Quantity per serving |
|---|---:|
| Coffee beans | 18 g |
| Condensed milk | 30 ml |
| Fresh milk | 100 ml |
| Ice | 150 g |
| Cup | 1 piece |

The quantities are configurable examples, not fixed business rules.

### 6.3 Consumption Calculation

For each completed order:

1. Identify the applicable recipe version for each menu item.
2. Multiply ingredient quantities by the number of servings.
3. Aggregate requirements for identical inventory items.
4. Calculate the required stock deductions.
5. Validate stock availability.
6. Calculate the cost of consumed inventory.
7. Record inventory movements.
8. Finalize the sale and associated financial records.

### 6.4 Transactional Requirements

When a sale is finalized, related database changes should be committed atomically whenever practical.

The operation must ensure that:

- Inventory balances and movement records remain consistent.
- The sale is not finalized if inventory processing fails.
- Failed operations do not leave partial deductions.
- Retrying the same completion request does not duplicate movements.
- Concurrent orders cannot oversell inventory when negative stock is disabled.

Use PostgreSQL transactions and appropriate row-level locking or conditional updates where needed.

SQLAlchemy session management must follow explicit transaction boundaries.

### 6.5 Stock Availability Policy

Default behavior: prevent finalization if required inventory is insufficient.

Display the unavailable items and required quantities.

Optionally support negative stock through a business configuration.

When negative stock is allowed:

- Record the resulting negative balance.
- Flag affected items.
- Handle missing inventory cost information explicitly.
- Ensure reports identify the resulting costing limitations.

### 6.6 Recipe Versioning

Historical orders must retain the recipe information used to calculate consumption.

Recipe updates must affect future applicable sales only.

Never reprocess completed historical orders merely because a recipe has changed.

### 6.7 Refunds and Returns

Refunding a customer must not automatically restore consumed ingredients.

Inventory restoration requires an explicit return or adjustment transaction.

Examples:

- Refund for a prepared drink: no automatic ingredient restoration.
- Return of an unopened bottled drink: restore stock if approved and sellable.
- Cancelled draft: no stock change.

### 6.8 Acceptance Criteria

- Ingredient consumption is calculated correctly.
- Quantities are aggregated before stock updates.
- Every deduction references its originating sale.
- Duplicate completion requests cannot deduct stock twice.
- Failed database transactions roll back related changes.
- Recipe changes preserve historical accuracy.
- Returns and refunds follow explicit stock rules.

---

## 7. Goal 4 — Basic Accounting

### 7.1 Objective

Provide financial visibility without implementing a full enterprise accounting system.

Users should be able to understand:

- Net sales.
- Recorded payments.
- Operating expenses.
- Supplier payables.
- Inventory consumption costs.
- Estimated gross profit.
- Estimated operating profit.

### 7.2 Income

Record finalized sales with:

- Transaction date.
- Order reference.
- Gross sales.
- Discounts.
- Refunds.
- Taxes, when applicable.
- Net sales.
- Payment status.

Do not count payment records as additional sales revenue.

Sales revenue and cash received must be reported separately when their timing differs.

### 7.3 Expenses

Allow users to record:

- Rent.
- Utilities.
- Salaries.
- Equipment.
- Maintenance.
- Marketing.
- Delivery costs.
- Other operating expenses.

Each expense must include category, amount, date, payment status, payment method, description, and responsible user.

### 7.4 Supplier Payables

Support:

- Unpaid purchases.
- Partial supplier payments.
- Full supplier payments.
- Outstanding balances.
- Purchase and payment history.

Receiving stock and paying a supplier are separate operations.

### 7.5 Cash and Bank Movements

Track recorded:

- Customer receipts.
- Supplier payments.
- Operating expenses paid.
- Refunds.
- Authorized cash adjustments.

The displayed balances must be based on recorded transactions and must not be presented as bank-reconciled balances unless reconciliation is implemented.

### 7.6 Inventory Costing

Use weighted-average inventory cost as the recommended initial valuation method.

The system must:

- Update costs when inventory is received.
- Calculate the cost of recipe ingredients consumed.
- Calculate the cost of directly sold inventory.
- Account for applicable inventory returns and adjustments.
- Preserve historical cost records.
- Handle negative stock and missing cost information explicitly.

### 7.7 Profit Calculations

**Net Sales**

Gross sales − Discounts − Sales refunds.

Taxes collected on behalf of tax authorities should be treated separately where applicable.

**Cost of Goods Sold**

The cost attributable to inventory consumed by finalized sales, adjusted for applicable returns and corrections.

**Gross Profit**

Net sales − Cost of Goods Sold.

**Estimated Operating Profit**

Gross profit − Recorded operating expenses.

These are operational management figures, not a substitute for complete statutory accounting or tax reporting.

### 7.8 Acceptance Criteria

- Sales are recorded once.
- Payments and refunds cannot be duplicated.
- Supplier purchases and payments remain distinguishable.
- Inventory consumption contributes to cost of goods sold.
- Expenses are categorized.
- Financial reports reconcile with source transactions.
- Posted transactions are corrected through auditable reversals.

---

## 8. Goal 5 — Sales Reports

### 8.1 Objective

Provide straightforward reports that help business owners understand sales performance, inventory usage, and profitability.

### 8.2 Dashboard

Display:

- Today's net sales.
- Today's completed order count.
- Average order value.
- Discounts.
- Refunds.
- Estimated cost of goods sold.
- Estimated gross profit.
- Recorded expenses.
- Estimated operating profit.
- Number of low-stock items.

Allow filtering by date range.

### 8.3 Sales Summary

Report:

- Gross sales.
- Discounts.
- Refunds.
- Net sales.
- Order count.
- Average order value.
- Sales by day, week, or month.
- Payment-method breakdown.

Allow filters by date, cashier, payment method, category, and order status.

### 8.4 Product Performance

Report:

- Product name.
- Quantity sold.
- Gross sales.
- Discounts.
- Net sales.
- Estimated cost.
- Estimated gross profit.
- Contribution to total net sales.

Identify best-selling and low-selling items.

### 8.5 Inventory and Consumption

Report:

- Current stock.
- Opening stock, when available.
- Stock received.
- Quantity consumed by sales.
- Adjustments.
- Returns.
- Closing stock.
- Estimated inventory value.

Distinguish recipe-based consumption from manual adjustments and spoilage.

### 8.6 Expense and Profit Reports

Report:

- Expenses by category.
- Net sales.
- Cost of goods sold.
- Gross profit.
- Estimated operating profit.
- Comparisons between selected periods.

### 8.7 Export

Provide CSV exports for supported reports.

Exports must respect user permissions and the selected report filters.

### 8.8 Acceptance Criteria

- Reports reconcile with source transactions.
- Draft and cancelled orders are excluded from completed sales.
- Refunds are handled consistently.
- Inventory consumption agrees with posted movements.
- Profit calculations follow the configured inventory valuation method.
- Date filters use consistent rules.
- CSV exports match the filtered report results.

---

## 9. Authentication and Authorization

### 9.1 Roles

Support the following initial roles:

| Role | Access |
|---|---|
| Owner / Administrator | Full application access. |
| Manager | Manage operations and view permitted reports. |
| Cashier | Create orders, record payments, and view permitted sales history. |
| Inventory Staff | Manage receipts, stock adjustments, and inventory history. |
| Accountant | Review financial records and reports. |

### 9.2 Security Requirements

- Protect application routes.
- Enforce permissions on the backend.
- Secure passwords using an established password-hashing implementation.
- Use bearer-token (JWT) authentication for the SPA, as provided by the template; because tokens are not sent as cookies, CSRF protection is not required unless cookie-based sessions are introduced.
- Protect state-changing browser requests against CSRF where applicable.
- Keep secrets in environment variables or a dedicated secrets manager.
- Validate inputs using Pydantic and domain-level validation.
- Avoid exposing sensitive information in logs.
- Restrict access to financial and inventory adjustments.

Reuse the chosen FastAPI template's existing security implementation if it meets these requirements.

---

## 10. Data Integrity and Auditability

### 10.1 Inventory Movements

Treat inventory movements as the auditable history of stock changes.

Maintain separate concepts for:

- Inventory movement history.
- Current inventory balance.
- Inventory valuation.

Every movement must reference its originating business transaction.

### 10.2 Idempotency

Critical operations must safely handle retries:

- Order completion.
- Payment recording.
- Stock receipt posting.
- Refund processing.
- Stock adjustment posting.

Use operation identifiers or equivalent database constraints to prevent duplicate business transactions.

### 10.3 Audit Trail

Record relevant changes to:

- Orders.
- Payments.
- Refunds.
- Stock receipts.
- Inventory adjustments.
- Recipes.
- Menu prices.
- Expenses.
- User permissions.

Include actor, timestamp, entity reference, and a description of the action.

### 10.4 Corrections

Posted business transactions must not be silently deleted.

Use explicit reversals or correcting transactions to preserve the audit trail.

### 10.5 Database Constraints

Enforce data integrity at the database level where practical.

Examples:

- Unique order references.
- Unique stock receipt references.
- Valid positive quantities where required.
- Valid transaction statuses.
- Foreign-key relationships.
- Unique idempotency keys within their defined scope.
- Appropriate constraints on monetary amounts and payment allocations.

Do not rely solely on form validation to protect financial or inventory records.

---

## 11. Web Interface Goals

### 11.1 General Layout

Provide a shared application layout containing:

- Navigation menu.
- Page title.
- User information.
- Main content area.
- Notifications.
- Basic responsive styling.

Keep navigation simple and consistent.

### 11.2 Main Pages

Implement the following pages:

| Page | Purpose |
|---|---|
| Dashboard | Business overview. |
| Menu | Manage sellable products and menu items. |
| Inventory | View and manage stock. |
| Stock Receipts | Record incoming inventory. |
| Stock Adjustments | Record physical counts and corrections. |
| Recipes | Configure ingredient consumption. |
| POS / Orders | Create and complete sales. |
| Order History | Search and review sales. |
| Payments and Refunds | Review financial transactions. |
| Expenses | Record operating expenses. |
| Suppliers | Manage suppliers and outstanding balances. |
| Sales Reports | Analyze sales and product performance. |
| Inventory Reports | Analyze stock levels and consumption. |
| Profit Reports | Review estimated profitability. |
| Users and Settings | Manage access and business configuration. |

### 11.3 Frontend Interaction

The React application provides interactive pages, for example:

- Updating order totals as items are added (from backend responses).
- Searching products.
- Loading report filters.
- Adding order items without reloading the page.
- Displaying stock availability.
- Showing confirmation dialogs.

The backend remains the source of truth for prices, totals, inventory, costs, statuses, permissions, and financial calculations. React never computes authoritative totals or stock; any value shown after a save comes from the API response, and the client may only display previews.

Do not depend on client-side state for critical business operations. Hiding a button in the UI is never the only protection; every rule is enforced by the API.

Critical actions (completing orders, payments, refunds, posting receipts, adjustments) send an idempotency key so retries and double clicks cannot duplicate them.

### 11.4 User Experience

- Minimize clicks for common POS operations.
- Display clear validation messages.
- Confirm destructive or financially significant actions.
- Provide searchable tables.
- Use pagination for large result sets.
- Display currency consistently in VND by default.
- Use the configured business timezone consistently.
- Ensure important workflows work on desktop and tablet screens.

---

## 12. Non-Functional Requirements

### 12.1 Performance

Initial targets under a defined representative test load:

- Common read requests: p95 under 500 ms.
- Common write requests: p95 under 1 second.
- Standard dashboard queries: p95 under 2 seconds.

These targets exclude external payment-provider latency.

Avoid unnecessary ORM queries and N+1 query patterns.

Add indexes based on query patterns and measured performance.

### 12.2 Reliability

- Use explicit database transaction boundaries.
- Roll back failed business operations.
- Prevent duplicate processing.
- Log critical failures.
- Support database backup and restoration.
- Handle concurrency-sensitive inventory updates correctly.

### 12.3 Maintainability

- Follow the selected FastAPI template's conventions.
- Separate routes, services, schemas, and persistence logic.
- Keep business rules testable without HTTP requests.
- Use Alembic migrations for schema changes.
- Use type hints.
- Keep dependencies minimal.
- Avoid unnecessary generic repository layers or abstraction frameworks.

### 12.4 Observability

Provide:

- Structured logs.
- Correlation IDs.
- Health checks.
- Database connectivity checks.
- Error tracking.
- Audit logs for critical transactions.

### 12.5 Data Protection

- Enforce authentication and authorization.
- Use HTTPS in deployed environments.
- Protect session cookies.
- Store secrets outside source control.
- Back up the database.
- Document recovery procedures.
- Restrict access to sensitive business information.

---

## 13. Testing Goals

Use pytest for automated testing.

### 13.1 Unit Tests

Test:

- Order total calculation.
- Discount validation.
- Recipe consumption calculations.
- Unit conversion.
- Inventory cost calculations.
- Profit calculations.
- Order state transitions.
- Permission checks.

### 13.2 Integration Tests

Test:

- Stock receipt posting.
- Order completion.
- Automatic inventory deduction.
- Payment recording.
- Refund processing.
- Expense recording.
- Supplier payments.
- Report calculations.

### 13.3 Transaction and Concurrency Tests

Verify that:

- Failed order completion does not leave partial stock movements.
- Duplicate requests do not create duplicate sales.
- Duplicate requests do not create duplicate payments.
- Concurrent sales do not oversell inventory when negative stock is disabled.
- Stock balances agree with movement records.
- Refunds do not automatically restore consumed ingredients.
- Database constraints protect critical invariants.

Use PostgreSQL integration tests for database behaviors that SQLite cannot accurately represent.

### 13.4 End-to-End Tests

Verify the complete workflow:

1. Create an inventory item.
2. Receive stock.
3. Create a recipe.
4. Create a menu item.
5. Complete a sale.
6. Verify automatic stock deduction.
7. Verify payment recording.
8. Verify cost of goods sold.
9. Verify sales reports.
10. Record an expense.
11. Verify estimated operating profit.

---

## 14. Implementation Phases

### Phase 1 — FastAPI Template and Foundation

- Select and initialize the FastAPI web template.
- Configure application settings.
- Configure PostgreSQL.
- Configure SQLAlchemy.
- Configure Alembic.
- Set up the React frontend, generated API client, and role-aware navigation.
- Implement authentication and authorization.
- Establish testing and logging conventions.

**Deliverable:** A working, deployable web application foundation.

### Phase 2 — Catalog and Inventory

- Implement categories and menu items.
- Implement inventory items.
- Implement suppliers.
- Implement stock receipts.
- Implement stock adjustments.
- Implement inventory movements and balances.
- Implement low-stock warnings.

**Deliverable:** Users can manage inventory and trace stock changes.

### Phase 3 — Ordering and Payments

- Implement the POS interface.
- Implement order creation.
- Implement order items and price snapshots.
- Implement payment recording.
- Implement order completion and cancellation.
- Implement refund workflows.
- Implement order history.

**Deliverable:** Users can process and review sales.

### Phase 4 — Recipes and Automatic Deduction

- Implement recipes and versioning.
- Implement ingredient calculations.
- Implement stock availability validation.
- Implement automatic deduction.
- Implement inventory costing.
- Implement idempotent order completion.
- Add concurrency tests.

**Deliverable:** Completed sales automatically update inventory and associated costs.

### Phase 5 — Accounting

- Implement expense management.
- Implement supplier payables.
- Implement supplier payments.
- Implement cash and bank movements.
- Implement cost of goods sold.
- Implement profit calculations.
- Implement transaction reversals.

**Deliverable:** Owners can review recorded income, expenses, outstanding supplier balances, and estimated profitability.

### Phase 6 — Reports

- Implement the dashboard.
- Implement sales summaries.
- Implement product performance reports.
- Implement inventory reports.
- Implement ingredient consumption reports.
- Implement expense and profit reports.
- Implement CSV export.

**Deliverable:** Owners can review operational and financial performance.

### Phase 7 — Hardening and Deployment

- Run automated tests.
- Validate transaction integrity.
- Test concurrency-sensitive operations.
- Verify report reconciliation.
- Test backup and restoration.
- Review authorization boundaries.
- Perform representative load testing.
- Document deployment and maintenance.

**Deliverable:** A reliable initial release ready for a small-business pilot.

---

## 15. Definition of Success

The initial release is successful when:

1. The FastAPI template runs reliably with PostgreSQL.
2. Users can manage products and inventory.
3. Supplier receipts and stock adjustments are traceable.
4. Users can create and complete orders.
5. Payments and refunds are recorded correctly.
6. Recipes define the ingredients required for menu items.
7. Completed sales automatically deduct the correct inventory.
8. Critical operations are protected against duplicate requests.
9. Inventory costing and cost of goods sold are calculated consistently.
10. Users can record expenses and track supplier payables.
11. Sales and financial reports reconcile with underlying transactions.
12. The application provides role-based access control.
13. Critical business workflows have automated tests.
14. The system can be deployed, backed up, and restored without unnecessary infrastructure complexity.

## 16. Final Product Vision

Build a lightweight FastAPI and React application that allows a small restaurant or café to manage its daily operations from one place.

The application must answer five questions:

1. **What do I have?** — Inventory management.
2. **What am I selling?** — Menu and ordering.
3. **What stock did I consume?** — Recipe-based automatic inventory deduction.
4. **How much did I earn and spend?** — Basic accounting.
5. **How is my business performing?** — Sales and profitability reports.

The initial release should prioritize reliable business workflows, data integrity, and ease of maintenance.

The primary success criterion is the ability to complete a sale, update inventory correctly, record its financial impact, and generate trustworthy reports through a simple web interface.