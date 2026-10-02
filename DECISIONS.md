# Technical Decisions

## Service boundaries

The invoice service owns vendors, invoices, invoice lines, invoice status, and the invoice outbox. The payment service owns payment runs, payments, and its invoice projection. Keeping those records in separate schemas lets each service own its data.

## Invoice event delivery

Invoice changes and their outbox events are written in the same database transaction. A worker publishes outbox events to Redis, and the payment service consumes them into its projection.

The payment consumer records processed event IDs so it can skip duplicate deliveries. This is necessary because stream delivery can happen more than once.

## Money representation

Amounts are stored and transferred as integer cents. This avoids rounding errors from floating-point arithmetic.

## Payment execution and retries

Each payment has a stable ID and idempotency key. The payment is marked in flight before calling the bank simulator.

A definitive simulator failure can be retried according to its documented behavior. If the network fails after submission, the outcome may be unknown. In that case, the system records `unknown` and reconciles against the bank ledger instead of blindly sending the transfer again.

## Aging report

The aging report uses one SQL query to calculate outstanding balances, assign aging buckets, return summary counts and amounts, and paginate the invoice rows. The report accepts an as-of date so results can be reproduced for a chosen date.