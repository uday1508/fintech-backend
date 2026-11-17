# Fintech Banking Platform — Backend Technical Design Specification

**Document type:** Backend Architecture & Technical Design  
**Version:** 1.0  
**Status:** Implementation specification  
**Backend:** Python + FastAPI  
**Database:** PostgreSQL  
**ORM:** SQLAlchemy 2.x  
**Migrations:** Alembic  
**Validation:** Pydantic  
**Testing:** pytest + HTTPX  
**Client:** React Native application with customer and merchant workspaces

---

# 1. Project Overview

## 1.1 Objective

Build a unified fintech platform that supports customer accounts, merchant accounts, internal payments, double-entry accounting, statement reconciliation, fraud detection, and financial recommendations.

The platform will expose a versioned REST API through FastAPI. A single React Native application will use this API and display different experiences based on the authenticated user's roles, permissions, and active workspace.

The initial implementation will be a simulated financial environment using synthetic users, accounts, transactions, and statement data.

## 1.2 Functional modules

The backend consists of eight principal modules:

1. Identity, authentication, and authorization.
2. Customer and merchant management.
3. Accounts and balance management.
4. Payment processing and double-entry ledger.
5. Statement reconciliation.
6. Fraud detection and review.
7. Customer recommendations and merchant analytics.
8. Audit logging and operational reporting.

These are logical modules inside one application, not independent microservices.

## 1.3 Architectural principles

The following principles are mandatory.

- **Single source of financial truth:** Posted ledger entries determine the authoritative financial position.
- **Canonical payment records:** A payment has one identity, regardless of how many modules consume it.
- **Atomic financial operations:** A financial operation must not leave partially committed journal entries.
- **Idempotent writes:** Repeated requests must not duplicate financial effects.
- **Explicit authorization:** Every protected operation verifies the authenticated principal, resource ownership, and required permission.
- **Immutable accounting history:** Posted journal entries cannot be edited or deleted.
- **Derived analytics:** Fraud scores, categories, and recommendations do not independently modify financial balances.
- **Auditable decisions:** Financial operations and important administrative actions retain traceable references.
- **Modular implementation:** Each business domain owns its models, services, and repository operations.
- **Incremental delivery:** The architecture must support a working portfolio MVP within 30 days without requiring distributed infrastructure.

---

# 2. High-Level Architecture

## 2.1 System architecture

```text
React Native Application
        |
        | HTTPS / JSON / Bearer Token
        v
FastAPI Application
        |
        +-- Authentication and Authorization
        +-- Users and Merchant Management
        +-- Account Management
        +-- Payment Orchestration
        +-- Double-Entry Ledger
        +-- Statement Reconciliation
        +-- Fraud Detection
        +-- Recommendations and Analytics
        +-- Audit Logging
        |
        v
PostgreSQL
        |
        +-- Identity and Access Tables
        +-- Account and Payment Tables
        +-- Ledger Tables
        +-- Reconciliation Tables
        +-- Fraud Tables
        +-- Analytics Tables
```

## 2.2 Architecture style

Use a **modular monolith with a layered architecture**.

The application should have four logical layers.

### API layer

Responsibilities:

- Define HTTP routes.
- Authenticate requests.
- Validate request and response schemas.
- Resolve permissions.
- Translate service results into HTTP responses.
- Apply pagination and filtering.

The API layer must not implement accounting rules or execute complex database transactions directly.

### Service layer

Responsibilities:

- Implement business workflows.
- Coordinate multiple repositories.
- Enforce domain invariants.
- Define transaction boundaries.
- Coordinate payment, ledger, fraud, and reconciliation operations.

Examples:

- `PaymentService`
- `LedgerService`
- `FraudService`
- `ReconciliationService`
- `RecommendationService`

### Repository/data-access layer

Responsibilities:

- Execute database queries.
- Persist and retrieve domain records.
- Apply resource-scoped filtering.
- Support locking and efficient query patterns.

Repositories must not commit financial transactions independently. The service layer controls the unit of work.

### Domain/model layer

Responsibilities:

- Define SQLAlchemy models.
- Define domain enums and constants.
- Express financial rules and domain-specific validation.
- Define shared domain types such as money amounts and account identifiers.

## 2.3 Dependency direction

Use this dependency direction:

```text
API -> Services -> Repositories -> Database

Services -> Domain rules
Services -> Other domain services when needed
```

Avoid circular dependencies. For example, the recommendation module can query posted payment and ledger data, but the ledger module must not depend on the recommendation module.

---

# 3. User, Role, Merchant, and Permission Model

## 3.1 Core concepts

The following entities must remain separate.

### User

Represents an authenticated person.

Examples:

- Customer using the app to make payments.
- Merchant owner.
- Merchant cashier.
- Merchant analyst.
- Platform administrator.

### Role

Represents a collection of capabilities.

Initial roles:

- `CUSTOMER`
- `MERCHANT_OWNER`
- `MERCHANT_CASHIER`
- `MERCHANT_ANALYST`
- `PLATFORM_ADMIN`

### Permission

Represents a specific action that a principal is allowed to perform.

Examples:

- `account.read_own`
- `payment.create`
- `payment.read_own`
- `merchant.payment.read`
- `merchant.refund.create`
- `merchant.analytics.read`
- `merchant.reconciliation.manage`
- `merchant.members.manage`
- `fraud.alert.review`

### Merchant

Represents a business receiving payments.

A merchant has its own identity, category, status, financial accounts, and analytics.

### Merchant membership

Connects a user to a particular merchant and defines the user's business-specific role.

The same person may own one merchant, work as a cashier for another merchant, and use the application as a customer.

Therefore, merchant membership must not be represented by a single global role column.

## 3.2 Required identity tables

### `users`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `full_name` | VARCHAR(150) | Required |
| `email` | VARCHAR(255) | Unique, normalized |
| `password_hash` | TEXT | Required |
| `status` | VARCHAR(30) | Active, suspended, disabled |
| `created_at` | TIMESTAMPTZ | Required |
| `updated_at` | TIMESTAMPTZ | Required |

Do not store plaintext passwords.

### `roles`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `code` | VARCHAR(50) | Unique |
| `name` | VARCHAR(100) | Required |

### `permissions`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `code` | VARCHAR(100) | Unique |
| `description` | TEXT | Optional |

### `user_roles`

- `user_id` — foreign key to users.
- `role_id` — foreign key to roles.
- Composite primary key on `(user_id, role_id)`.

### `role_permissions`

- `role_id` — foreign key to roles.
- `permission_id` — foreign key to permissions.
- Composite primary key on `(role_id, permission_id)`.

### `merchants`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | VARCHAR(200) | Required |
| `category_id` | UUID | Foreign key |
| `status` | VARCHAR(30) | Required |
| `created_at` | TIMESTAMPTZ | Required |
| `updated_at` | TIMESTAMPTZ | Required |

### `merchant_memberships`

- `id` — UUID primary key.
- `merchant_id` — foreign key.
- `user_id` — foreign key.
- `role_id` — merchant-specific role.
- `status` — active, invited, suspended, or revoked.
- `created_at` and `updated_at`.

Add a uniqueness constraint appropriate to your membership policy, such as one active membership per user and merchant.

## 3.3 Authorization rules

Every protected API must determine:

1. Who is making the request?
2. Which permission is required?
3. Which resource is being accessed?
4. Does the user own the resource or have an active membership with the required permission?
5. Is the resource in a valid state for the requested operation?

The React Native app may hide inaccessible screens, but frontend visibility is not a security boundary.

Use `401 Unauthorized` for missing or invalid authentication and `403 Forbidden` when an authenticated user lacks the required permission. A `404 Not Found` response may be preferable for resource lookups where revealing existence would expose another tenant's data.

---

# 4. Merchant Categories and Business Configuration

## 4.1 Merchant category model

Create a `merchant_categories` table rather than hardcoding business types into application logic.

Suggested columns:

- `id`
- `parent_id`, nullable
- `code`, unique
- `name`
- `is_active`
- `created_at`

Example hierarchy:

```text
Food and Beverage
  Restaurant
  Cafe
  Bakery

Automotive
  Fuel Station
  EV Charging
  Vehicle Service

Transport
  Taxi
  Bus
  Vehicle Rental

Retail
  Grocery
  Clothing
  Electronics

Healthcare
  Pharmacy
  Clinic
  Diagnostics
```

The hierarchy supports reporting at different levels.

For example, a merchant can be classified as a cafe, while the recommendation engine aggregates sales across all food and beverage businesses.

## 4.2 Category ownership

The merchant's category describes the business, not the category of every payment.

A restaurant may receive a payment for a meal, a delivery charge, or a refund. Customer transaction categorization may use the merchant's category as its initial classification, but the transaction category should remain a separate record.

This distinction enables later support for item-level purchases, merchant-specific products, and customer-defined categories.

---

# 5. Accounts and Money Representation

## 5.1 Account model

Create an `accounts` table for customer-facing and merchant-facing financial accounts.

Recommended columns:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `account_number` | VARCHAR | Unique public account reference |
| `owner_user_id` | UUID, nullable | Customer ownership |
| `owner_merchant_id` | UUID, nullable | Merchant ownership |
| `currency` | CHAR(3) | For example, INR |
| `status` | VARCHAR(30) | Active, frozen, closed |
| `available_balance_minor` | BIGINT | Optional balance cache |
| `created_at` | TIMESTAMPTZ | Required |
| `updated_at` | TIMESTAMPTZ | Required |

For the MVP, use an explicit ownership design that guarantees exactly one valid owner type. This can be implemented with separate ownership tables or a constrained account-owner structure. Do not allow both owner fields to be populated, or neither to be populated.

The account's currency must be explicit. Do not assume every account uses INR forever.

## 5.2 Money representation

Represent monetary amounts in integer minor units.

For example:

- ₹100.00 = `10000` paise.
- ₹650.00 = `65000` paise.
- ₹1,000.00 = `100000` paise.

Use an application-level money type that carries both amount and currency.

Never use Python floating-point arithmetic for money.

All database calculations must respect the currency and its minor-unit precision.

## 5.3 Available balance and ledger balance

Distinguish between:

- **Ledger balance:** the account's financial position derived from posted journal entries.
- **Available balance:** the amount currently available to spend, considering the product's hold and pending-payment rules.
- **Cached balance:** a stored projection used to improve read performance.

The ledger is authoritative. A cached balance must be reconcilable against the ledger and must never become an independent source of truth.

For the initial implementation, avoid introducing complex holds unless needed. If holds are added, model them explicitly rather than pretending pending payments are already posted.

---

# 6. Double-Entry Ledger

This is the most critical backend module.

## 6.1 Purpose

The ledger records the financial effects of each successful financial operation.

The payment table describes a business event. The ledger describes the accounting impact of that event.

A payment can have one or more journal transactions, and each journal transaction contains two or more ledger entries.

## 6.2 Ledger tables

### `ledger_accounts`

Represents accounting accounts rather than customer login accounts.

Recommended columns:

- `id`
- `code`, unique
- `name`
- `account_type`
- `normal_balance`
- `currency`
- `owner_account_id`, nullable
- `owner_merchant_id`, nullable
- `is_active`
- `created_at`

Initial account types:

- `ASSET`
- `LIABILITY`
- `EQUITY`
- `REVENUE`
- `EXPENSE`

For a simplified wallet model, customer and merchant wallet balances are represented as liabilities of the platform.

### `ledger_transactions`

Recommended columns:

- `id`
- `reference`
- `source_type`
- `source_id`
- `status`
- `currency`
- `description`
- `posted_at`
- `created_at`
- `created_by`

Use a unique constraint on the accounting operation's stable reference to prevent duplicate posting.

Suggested statuses:

- `DRAFT`
- `POSTED`
- `REVERSED`

A reversed journal must remain in history. A correction is represented by a new linked journal transaction.

### `ledger_entries`

Recommended columns:

- `id`
- `ledger_transaction_id`
- `ledger_account_id`
- `direction`
- `amount_minor`
- `currency`
- `created_at`

Allowed directions are `DEBIT` and `CREDIT`.

Require a strictly positive entry amount. Represent the direction separately rather than using negative values.

## 6.3 Accounting invariants

For every posted journal transaction:

1. There must be at least two entries.
2. Total debits must equal total credits for each currency.
3. Every referenced ledger account must be valid and active according to posting policy.
4. The transaction must not be posted more than once.
5. Posted entries cannot be edited or deleted.
6. Every reversal must reference the original transaction.
7. The original journal and reversal must remain independently auditable.

Use a database transaction for posting. Do not rely solely on a Pydantic validator to maintain accounting invariants.

## 6.4 Example: customer pays merchant ₹650

Assume both parties hold simulated wallet balances on the platform.

| Ledger account | Debit | Credit |
|---|---:|---:|
| Customer wallet liability | ₹650 | — |
| Merchant wallet liability | — | ₹650 |

A debit decreases the customer liability, and a credit increases the merchant liability.

The ledger transaction must balance before it can be marked `POSTED`.

## 6.5 Ledger posting service

Create a reusable service with an interface conceptually similar to:

```python
async def post_journal(
    session,
    reference,
    currency,
    entries,
):
    ...
```

The service must:

1. Validate the reference and input entries.
2. Lock or safely serialize any relevant accounting state.
3. Validate currency consistency.
4. Verify that total debits equal total credits.
5. Verify the operation has not already been posted.
6. Insert the journal transaction and its entries.
7. Update any permitted balance projections.
8. Commit through the calling service's transaction boundary.

The example is an interface sketch, not a complete implementation.

Repositories must not independently commit journal entries. The service coordinating the financial operation controls the transaction.

## 6.6 Balance computation

The balance of a ledger account depends on its normal accounting side.

For liability accounts, a credit balance generally represents an increased liability. For assets, a debit balance generally represents an increased asset.

Implement a consistent accounting-balance calculation and test it against known journal fixtures.

Do not simply sum all debits or all credits without considering account type.

---

# 7. Payment Engine

## 7.1 Purpose

The payment engine coordinates the business lifecycle of a transfer or merchant purchase.

It must not directly mutate financial balances without corresponding ledger postings.

## 7.2 `payments` table

Recommended columns:

- `id`
- `reference`
- `payer_account_id`
- `payee_account_id`
- `merchant_id`, nullable where appropriate
- `amount_minor`
- `currency`
- `status`
- `idempotency_key`
- `created_by_user_id`
- `created_at`
- `updated_at`
- `posted_at`
- `failure_code`, nullable

Use a unique payment reference and a unique idempotency key scoped to the authenticated user or API client.

The key must be stored and enforced by PostgreSQL, not only checked in application memory.

## 7.3 Payment statuses

Suggested states:

```text
INITIATED
   |
   v
PENDING_REVIEW
   |
   +----> FAILED
   |
   +----> BLOCKED
   |
   v
APPROVED
   |
   v
POSTED
   |
   v
PARTIALLY_REFUNDED
   |
   v
REFUNDED
```

Not every payment follows every state.

For example, a payment that does not require review can move directly from initiation to approval and posting.

A blocked payment must not create completed payment ledger postings.

Keep reversal and refund semantics explicit. A failed payment attempt, a successful refund, and an accounting reversal are different business events.

## 7.4 Payment processing sequence

For a simple internal wallet transfer:

1. Authenticate the caller.
2. Validate the idempotency key.
3. Return the existing result if the same key was previously processed.
4. Validate amount, currency, account ownership, account status, and destination.
5. Create or load the payment record.
6. Evaluate fraud rules.
7. Reject, queue for review, or proceed according to the fraud decision.
8. Lock affected accounts in a deterministic order to reduce deadlocks.
9. Recheck the spendable balance under the appropriate locks.
10. Create balanced journal entries.
11. Update the payment status and permitted balance projections.
12. Commit the payment and ledger changes atomically.
13. Return the canonical payment reference and status.

For the initial MVP, keep internal payments within a single PostgreSQL transaction after risk assessment. If you later integrate an external payment provider, do not hold a database transaction open during a network request. Use explicit pending states, an outbox, idempotent provider requests, and reconciliation to manage the external workflow.

## 7.5 Idempotency

A retry must not create a second financial movement.

If a request times out after the database commits, a repeated request with the same idempotency key must return the original result.

If the same key is reused with a different request payload, return a conflict response.

Store a normalized request fingerprint or equivalent payload comparison with the idempotency record.

## 7.6 Payment failure handling

The implementation must handle:

- Insufficient funds.
- Inactive accounts.
- Blocked fraud decisions.
- Review-pending decisions.
- Duplicate requests.
- Concurrent transfers.
- Database failures.
- Invalid currencies.
- Invalid merchant ownership.
- Duplicate ledger posting attempts.

Financial failures must not leave partial journal postings.

---

# 8. Refunds and Reversals

## 8.1 Refund model

Create a `refunds` table with:

- `id`
- `reference`
- `original_payment_id`
- `amount_minor`
- `currency`
- `status`
- `requested_by_user_id`
- `reason_code`
- `created_at`
- `completed_at`

Enforce the rule that cumulative successful refunds cannot exceed the original eligible payment amount.

Refunds should be idempotent and independently auditable.

## 8.2 Refund accounting

A refund creates new linked journal entries that reverse the relevant financial effect, using the appropriate accounting model.

Do not delete the original payment or its posted journal.

For partial refunds, calculate the remaining refundable amount safely under concurrency.

For the initial platform, refunds can be approved and posted within the simulated wallet environment. External settlement refunds are out of scope until a payment-provider integration is introduced.

---

# 9. Statement Reconciliation

## 9.1 Purpose

Reconciliation compares external financial records with internal payment, settlement, and ledger records.

A statement line is evidence of an external event. Importing a line must not automatically create a new customer payment.

## 9.2 Tables

### `statement_imports`

Fields:

- `id`
- `merchant_id` or account scope
- `file_name`
- `file_hash`
- `status`
- `total_lines`
- `matched_lines`
- `unmatched_lines`
- `created_by_user_id`
- `created_at`
- `completed_at`

Use a unique file hash within the appropriate import scope to detect accidental duplicate imports.

### `statement_lines`

Fields:

- `id`
- `statement_import_id`
- `external_reference`
- `transaction_date`
- `amount_minor`
- `currency`
- `description`
- `status`
- `created_at`

### `reconciliation_matches`

Fields:

- `id`
- `statement_line_id`
- `internal_reference`
- `match_type`
- `status`
- `confidence`
- `reviewed_by_user_id`
- `created_at`
- `resolved_at`

Define uniqueness rules appropriate to the reconciliation process so one statement line cannot accidentally be matched to multiple incompatible financial events.

## 9.3 Matching algorithm

Use the following order:

1. Exact external reference.
2. Exact amount and currency.
3. Date or settlement-window compatibility.
4. Account or merchant scope compatibility.
5. Additional matching rules when necessary.

Do not automatically mark an ambiguous match as successful.

Suggested results:

- `MATCHED`
- `UNMATCHED`
- `POTENTIAL_MATCH`
- `AMOUNT_MISMATCH`
- `DUPLICATE`
- `MANUAL_REVIEW`

For the 30-day MVP, implement CSV import and deterministic matching. Use a synthetic statement format that documents whether the amounts represent individual payments, settlement batches, fees, or net deposits.

If the statement represents settlement batches, compare it to settlement records or aggregates rather than assuming every line corresponds to an individual customer payment.

## 9.4 Reconciliation invariants

- Duplicate imports must be detected.
- Original imported data must be preserved.
- A mismatch must not silently modify the ledger.
- Manual resolutions must record the reviewer and reason.
- Matching logic must be repeatable and auditable.
- Statement data must be isolated by merchant or account authorization.

---

# 10. Fraud Detection Engine

## 10.1 Purpose

The fraud module evaluates payment attempts and stores risk decisions.

The first version uses configurable rules rather than machine learning.

## 10.2 Tables

### `fraud_assessments`

Fields:

- `id`
- `payment_id`
- `risk_score`
- `decision`
- `rule_version`
- `reasons`
- `created_at`

### `fraud_alerts`

Fields:

- `id`
- `fraud_assessment_id`
- `status`
- `assigned_to_user_id`, nullable
- `resolution_code`, nullable
- `resolution_notes`, nullable
- `created_at`
- `resolved_at`

Suggested decisions:

- `ALLOW`
- `REVIEW`
- `BLOCK`

## 10.3 Initial rules

Implement configurable rules for:

- Unusually large transaction amounts.
- Excessive transfer frequency.
- Multiple repeated attempts.
- Sudden changes in account activity.
- Repeated failed payment attempts.
- Risky destination patterns based on synthetic data.

Each rule must have an identifier, version, threshold, and explanation.

## 10.4 Fraud processing workflow

1. Receive a payment attempt.
2. Load relevant authorized transaction history.
3. Calculate features and evaluate configured rules.
4. Persist the risk assessment.
5. Apply the payment policy.
6. Allow, queue for review, or block the attempt.
7. Record any subsequent review decision.
8. Preserve the relationship between the assessment and the payment.

For the MVP, perform rule evaluation synchronously using a bounded amount of data. More advanced features such as rolling-window caches and asynchronous analysis can be added later.

Do not claim that arbitrary thresholds make a system production-ready. Real fraud models require calibration, evaluation, monitoring, and controls against abuse.

---

# 11. Transaction Categorization and Recommendation Engine

## 11.1 Purpose

The recommendation engine uses canonical financial records to provide different insights to customers and merchants.

It does not own or modify the underlying payment amounts.

## 11.2 Transaction categorization

Create a `transaction_categories` table with:

- `id`
- `payment_id`
- `category_id`
- `classification_source`
- `confidence`, nullable
- `created_at`

Possible classification sources:

- `MERCHANT_CATEGORY`
- `RULE_BASED`
- `USER_CORRECTED`
- `MODEL_PREDICTED`

Use a clear policy for whether a payment can have one primary category or multiple tags.

For the MVP, use one primary category per payment.

## 11.3 Customer recommendation data

Customer insights may include:

- Total spending by period.
- Spending by category.
- Month-over-month changes.
- Budget utilization.
- Recurring-payment candidates.
- Unusual spending patterns.
- Savings suggestions based on the user's own spending.

Create a `budgets` table with:

- `id`
- `user_id`
- `category_id`, nullable
- `period`
- `limit_minor`
- `currency`
- `created_at`
- `updated_at`

Customer insights must include only eligible transactions belonging to that customer's authorized accounts.

## 11.4 Merchant recommendation data

Merchant insights may include:

- Gross sales volume.
- Net sales after refunds.
- Number of successful payments.
- Average payment amount.
- Sales by time of day.
- Sales by merchant category or product category.
- Refund rate.
- Repeat-customer metrics.
- Low-demand period suggestions.

Merchant queries must be scoped to the authorized merchant ID.

## 11.5 Recommendation storage

Create a `recommendations` table with:

- `id`
- `target_type`
- `target_user_id`, nullable
- `target_merchant_id`, nullable
- `recommendation_type`
- `title`
- `description`
- `period_start`
- `period_end`
- `evidence`
- `status`
- `created_at`
- `expires_at`, nullable

Enforce a valid target model so a recommendation is not ambiguously assigned to a customer and a merchant at the same time.

The `evidence` field can store structured JSON describing the aggregated values used to generate the recommendation. It should not contain unnecessary personal information.

## 11.6 Recommendation calculation rules

- Include posted payments only.
- Exclude failed and blocked attempts.
- Treat refunds as adjustments rather than ignoring them.
- Do not count both debit and credit ledger entries as separate expenses.
- Avoid counting transfers between a customer's own accounts as purchases.
- Use consistent reporting periods and time zones.
- Avoid exposing identifiable customer information to merchants.
- Use minimum sample sizes for sensitive aggregate metrics when appropriate.

For the first month, use deterministic rules and SQL aggregation. A machine-learning recommendation model is a later enhancement, not a prerequisite.

---

# 12. Audit Logging

Create an `audit_logs` table for security-sensitive and operational events.

Recommended fields:

- `id`
- `actor_user_id`, nullable for system actions
- `action`
- `resource_type`
- `resource_id`
- `merchant_id`, nullable
- `correlation_id`
- `metadata`
- `created_at`

Examples:

- Merchant membership created or revoked.
- Refund approved.
- Fraud alert reviewed.
- Statement mismatch resolved.
- Merchant permissions changed.
- Payment blocked by a fraud rule.

Never log passwords, access tokens, full payment credentials, or other secrets.

Audit records should be append-only under the application's normal permissions. For a stronger implementation, restrict database access so the application role cannot modify or delete audit history.

---

# 13. REST API Specification

All routes must be versioned under `/api/v1`.

Use JSON request and response bodies, consistent error structures, pagination, and server-side authorization.

## 13.1 Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/auth/register` | Register a user |
| POST | `/api/v1/auth/login` | Authenticate |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Revoke refresh session |
| GET | `/api/v1/me` | Current authenticated user |
| GET | `/api/v1/me/workspaces` | Authorized customer and merchant workspaces |

Never accept a client-provided user ID as proof of identity.

## 13.2 Accounts

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/accounts` | List authorized accounts |
| GET | `/api/v1/accounts/{account_id}` | Account details |
| GET | `/api/v1/accounts/{account_id}/balance` | Balance details |
| GET | `/api/v1/accounts/{account_id}/transactions` | Account transaction history |

The backend must scope every account lookup to the authenticated principal's permissions.

## 13.3 Merchants

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/merchants` | Create merchant profile |
| GET | `/api/v1/merchants/{merchant_id}` | Merchant details |
| GET | `/api/v1/merchants/{merchant_id}/members` | Authorized member listing |
| POST | `/api/v1/merchants/{merchant_id}/members` | Add or invite a member |
| PATCH | `/api/v1/merchants/{merchant_id}/members/{membership_id}` | Change membership status or role |
| GET | `/api/v1/merchant-categories` | List supported categories |

Merchant membership changes require the appropriate business permissions.

## 13.4 Payments

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/payments` | Initiate a merchant payment |
| GET | `/api/v1/payments/{payment_id}` | Payment details |
| GET | `/api/v1/payments` | Authorized payment listing |
| POST | `/api/v1/payments/{payment_id}/refunds` | Request a refund |
| GET | `/api/v1/refunds/{refund_id}` | Refund status |
| GET | `/api/v1/transactions` | Authorized transaction history |

Require an `Idempotency-Key` header for financial write operations.

## 13.5 Ledger

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/ledger/transactions/{id}` | Journal details |
| GET | `/api/v1/ledger/accounts/{id}/entries` | Authorized ledger entries |
| GET | `/api/v1/ledger/reconciliation` | Internal ledger consistency report |

Ledger inspection endpoints should be restricted to the relevant customer, merchant, or administrative permissions. Do not expose the entire platform ledger to ordinary customers.

## 13.6 Reconciliation

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/merchant/{merchant_id}/statements/import` | Import statement CSV |
| GET | `/api/v1/merchant/{merchant_id}/statements` | Import history |
| GET | `/api/v1/merchant/{merchant_id}/statements/{id}` | Import details |
| GET | `/api/v1/merchant/{merchant_id}/reconciliation` | Matching results |
| POST | `/api/v1/merchant/{merchant_id}/reconciliation/{match_id}/resolve` | Resolve a discrepancy |

Validate file size, encoding, column names, row counts, numeric amounts, currencies, and duplicate references. Treat uploaded files as untrusted input.

## 13.7 Fraud

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/fraud/alerts` | Authorized alert listing |
| GET | `/api/v1/fraud/alerts/{alert_id}` | Alert details |
| POST | `/api/v1/fraud/alerts/{alert_id}/resolve` | Resolve a review |
| GET | `/api/v1/fraud/assessments/{id}` | Authorized assessment details |

Do not expose sensitive internal risk rules to every customer or merchant.

## 13.8 Recommendations and analytics

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/customer/insights/spending` | Customer spending analytics |
| GET | `/api/v1/customer/recommendations` | Customer recommendations |
| GET | `/api/v1/merchant/{merchant_id}/analytics/summary` | Merchant overview |
| GET | `/api/v1/merchant/{merchant_id}/analytics/sales` | Sales trends |
| GET | `/api/v1/merchant/{merchant_id}/analytics/categories` | Category breakdown |
| GET | `/api/v1/merchant/{merchant_id}/recommendations` | Merchant recommendations |

Require explicit date ranges or documented defaults. Apply the appropriate account or merchant scope before aggregation.

---

# 14. API Conventions

## 14.1 Response format

Use a consistent response structure.

Example successful response:

```json
{
  "data": {
    "payment_id": "uuid",
    "reference": "PAY-REFERENCE",
    "amount_minor": 65000,
    "currency": "INR",
    "status": "POSTED"
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

Example error response:

```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "The account has insufficient available funds.",
    "request_id": "uuid"
  }
}
```

These are illustrative contracts. Define exact response schemas with Pydantic.

## 14.2 HTTP status conventions

- `200 OK`: successful read or operation.
- `201 Created`: resource created.
- `202 Accepted`: asynchronous operation accepted but not completed.
- `400 Bad Request`: invalid business request.
- `401 Unauthorized`: authentication required or invalid.
- `403 Forbidden`: insufficient permission.
- `404 Not Found`: resource unavailable or intentionally concealed.
- `409 Conflict`: idempotency conflict or incompatible state transition.
- `422 Unprocessable Entity`: request schema or validation failure.
- `429 Too Many Requests`: rate limit exceeded.
- `500 Internal Server Error`: unexpected failure.

Do not return raw SQL errors, stack traces, secrets, or internal risk details in public API responses.

## 14.3 Pagination

Use cursor pagination for large transaction histories if practical. Offset pagination is acceptable for the initial MVP when ordering is deterministic.

Always use a stable ordering, such as `(created_at, id)`, and enforce a maximum page size.

---

# 15. Database Transaction Boundaries

## 15.1 Transaction ownership

The service coordinating a financial operation owns the database transaction.

A typical flow:

```text
API route
  |
  v
PaymentService
  |
  +-- Validate request
  +-- Evaluate fraud policy
  +-- Lock accounts
  +-- Recheck available funds
  +-- Create payment
  +-- Post journal
  +-- Update balance projection
  +-- Update payment status
  |
  v
Single database commit
```

Use SQLAlchemy's transaction management consistently. Avoid nested service functions that commit independently.

## 15.2 Concurrency control

Use row-level locks or another proven concurrency-control approach for transfers that depend on available balances.

When locking multiple accounts, lock them in a consistent order to reduce deadlocks.

The available-balance check must happen inside the protected transaction, not only before it.

## 15.3 Uniqueness and integrity

Use PostgreSQL constraints for:

- Unique payment references.
- Unique idempotency keys within the required scope.
- Unique ledger posting references.
- Valid foreign keys.
- Valid ownership relationships.
- Valid membership relationships.
- Positive monetary amounts.
- Consistent journal currency.
- Valid status values where appropriate.

Application-level validation improves error messages; database constraints protect integrity under concurrent requests.

---

# 16. FastAPI Backend Directory Structure

Use a feature-oriented directory structure.

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── permissions.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── db/
│   │   ├── session.py
│   │   └── base.py
│   ├── common/
│   │   ├── enums.py
│   │   ├── money.py
│   │   ├── pagination.py
│   │   └── idempotency.py
│   ├── auth/
│   ├── users/
│   ├── merchants/
│   ├── accounts/
│   ├── payments/
│   ├── ledger/
│   ├── refunds/
│   ├── reconciliation/
│   ├── fraud/
│   ├── recommendations/
│   ├── reporting/
│   └── audit/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── api/
├── scripts/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```

Each business module should contain its own models, schemas, repositories, services, and routes where needed.

For example:

```text
payments/
├── models.py
├── schemas.py
├── repository.py
├── service.py
├── router.py
├── enums.py
└── exceptions.py
```

Avoid creating excessive abstraction layers for simple CRUD operations. Use the same conventions across modules, but introduce abstractions when they improve consistency or testability.

---

# 17. Authentication and Security Requirements

## 17.1 Authentication

Implement:

- Password hashing with a modern password-hashing algorithm.
- Short-lived access tokens.
- Refresh-token rotation and revocation.
- Secure session handling.
- Authentication dependencies in FastAPI.
- Rate limits on authentication endpoints.

For the React Native app, store sensitive tokens in platform-secure storage rather than ordinary AsyncStorage.

## 17.2 Authorization

Implement centralized permission dependencies and resource-scoped service/repository checks.

Do not rely on role names sent by the client. The server determines roles and permissions from authenticated identity and current membership records.

For every merchant-scoped endpoint, verify that the authenticated user has an active membership for the requested merchant and the necessary permission.

## 17.3 Input and operational security

- Validate all input with Pydantic.
- Keep secrets in environment variables or a secret manager.
- Never commit `.env` files containing real secrets.
- Apply upload size and content limits.
- Use HTTPS in deployed environments.
- Avoid exposing personal data in logs.
- Use correlation IDs for troubleshooting.
- Configure CORS narrowly.
- Add rate limiting and abuse protection.
- Keep dependencies updated.
- Avoid returning sensitive internal details in error messages.

This is a portfolio design, not a substitute for production security reviews, financial regulations, or certification.

---

# 18. Testing Strategy

Use pytest with unit tests, API tests, and PostgreSQL integration tests.

## 18.1 Unit tests

Test:

- Money conversion and validation.
- Debit/credit balance calculation.
- Journal balancing.
- Payment state transitions.
- Fraud rule evaluation.
- Category aggregation.
- Recommendation generation.
- Statement matching.

## 18.2 Integration tests

Test:

- Database constraints.
- Atomic journal posting.
- Rollback on failure.
- Idempotency under retries.
- Concurrent transfer behavior.
- Refund limits.
- Duplicate statement imports.
- Merchant membership permissions.
- Reconciliation matching and resolution.

## 18.3 API tests

Test:

- Authentication and token expiry.
- Unauthorized requests.
- Cross-customer access attempts.
- Cross-merchant access attempts.
- Customer versus merchant workspace access.
- Payment creation and status retrieval.
- Fraud review authorization.
- Recommendation filtering.
- CSV upload validation.

Use a real PostgreSQL test database for locking and transactional behavior. SQLite alone cannot verify PostgreSQL-specific concurrency behavior.

---

# 19. Deployment and Configuration

## 19.1 Required environment variables

Example `.env.example`:

```text
APP_ENV=development
APP_NAME=fintech-platform
API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/fintech

JWT_SECRET_KEY=replace-with-a-generated-secret
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

LOG_LEVEL=INFO
MAX_UPLOAD_SIZE_MB=10
```

These are development configuration examples. Generate real secrets and do not use example credentials in deployment.

Use a dedicated database migration command rather than automatically running schema changes on every application startup.

## 19.2 Deployment components

The initial deployment needs:

- FastAPI application.
- PostgreSQL database.
- Migration workflow.
- Environment-specific configuration.
- Health endpoint.
- Structured logging.
- Automated tests in CI.

Redis and background workers can be introduced later for scheduled analytics, asynchronous imports, and larger workloads.

## 19.3 Health endpoints

Implement:

- `GET /health/live`: confirms the application process is alive.
- `GET /health/ready`: confirms that required dependencies, including PostgreSQL, are available.

Do not expose database credentials, sensitive configuration, or internal infrastructure details in these responses.

---

# 20. Thirty-Day Implementation Sequence

## Week 1: Foundation

**Days 1–7**

- Initialize FastAPI and PostgreSQL.
- Set up SQLAlchemy and Alembic.
- Build user, role, permission, merchant, membership, and account models.
- Implement authentication.
- Implement role and resource authorization.
- Connect the first React Native login and workspace screens.

**Exit criteria:** Customers and merchant staff can authenticate, and protected APIs enforce their permissions.

## Week 2: Financial core

**Days 8–14**

- Implement ledger accounts and journal entries.
- Build the reusable ledger posting service.
- Implement customer-to-merchant simulated payments.
- Add idempotency and concurrency-safe balance checks.
- Implement refunds and transaction history.
- Integrate payment flows into the mobile app.

**Exit criteria:** Payments work end to end, journal entries balance, and retries cannot duplicate financial effects.

## Week 3: Financial intelligence

**Days 15–21**

- Implement CSV statement imports.
- Build deterministic reconciliation.
- Implement configurable fraud rules.
- Add fraud assessments and review workflow.
- Build transaction categorization.
- Implement customer spending recommendations.
- Implement merchant sales analytics and recommendations.

**Exit criteria:** All analytical modules use shared canonical payment data and respect data-access boundaries.

## Week 4: Completion

**Days 22–30**

- Finish customer screens.
- Finish merchant screens.
- Integrate reconciliation and fraud interfaces.
- Add charts and recommendations.
- Run financial and authorization tests.
- Harden error handling and logging.
- Configure deployment and CI.
- Complete documentation and an end-to-end demo.

**Exit criteria:** A reviewer can run the project, log in as different roles, make a simulated payment, inspect its ledger, reconcile a statement, trigger a fraud rule, and view different customer and merchant insights.

---

# 21. Final Acceptance Criteria

The backend is ready for portfolio demonstration only when the following are true.

### Identity and access

- A user can have customer access and multiple merchant memberships.
- Merchant owners and cashiers have different permissions.
- All protected endpoints enforce authorization server-side.
- Cross-merchant data access is denied.

### Financial correctness

- Every posted journal transaction balances.
- Payment and ledger writes are atomic.
- Repeated requests do not duplicate transfers.
- Concurrent transfers cannot overspend the available balance.
- Refunds and reversals preserve accounting history.
- Balance projections can be reconciled against the ledger.

### Reconciliation and fraud

- Duplicate statement imports are detected.
- Unmatched records remain visible for investigation.
- Reconciliation never silently adjusts balances.
- Fraud assessments are persisted and linked to payment attempts.
- Blocked or review-pending payments do not receive completed postings.

### Recommendations and analytics

- Customer spending reports use only authorized customer data.
- Merchant reports use only the selected merchant's data.
- Failed transactions are excluded from posted spending totals.
- Refunds and internal transfers are handled consistently.
- Recommendations have traceable evidence and reporting periods.

### Delivery

- Database migrations run from a clean database.
- Tests cover financial invariants and permissions.
- The application starts from documented setup instructions.
- The mobile app can demonstrate the complete customer-to-merchant flow.
- The repository contains architecture documentation, API contracts, sample data, and a demo guide.

---

# 22. Engineering Decisions to Preserve Throughout Implementation

1. Start with a modular monolith; do not split into microservices during the first month.
2. Treat the ledger as the financial source of truth.
3. Treat payment records as the canonical business events consumed by other modules.
4. Enforce idempotency and concurrency safety in the database-backed service layer.
5. Keep posted accounting history immutable.
6. Make all merchant analytics tenant-scoped and permission-checked.
7. Use explainable fraud rules before adding machine learning.
8. Build recommendations from posted financial data rather than duplicated payment records.
9. Prefer reliable, tested financial flows over advanced UI polish or unnecessary infrastructure.
10. Keep the first release simulated; integrate actual financial providers only after the core design and operational requirements are understood.

**The implementation priority is identity and data ownership first, ledger correctness second, payment integration third, and reconciliation, fraud, and recommendations afterward.** Following that sequence will give you a coherent, testable backend rather than a collection of disconnected endpoints.
