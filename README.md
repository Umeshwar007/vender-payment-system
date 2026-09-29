
## Service ownership

- `invoice_service` owns vendors, invoices, invoice lines, and invoice status.
- `payment_service` owns payment runs and payments. It keeps a local projection of scheduled invoices.
- `bank_simulator` acts as the external bank and deliberately does not deduplicate transfers.
- `frontend` is the React application.

Invoice status changes will be recorded with an outbox entry in the same database transaction.
A worker will publish that entry through Redis Streams. The payment service consumes the
message and updates its own projection; it does not query invoice-service tables.

## Important retry constraint

The payment service will make requests locally idempotent and prevent two runs from reserving
the same invoice. But if a non-idempotent bank accepts a transfer and the response is lost,
blindly retrying could pay twice. Ambiguous attempts must be held for reconciliation unless
the bank provides a way to check or deduplicate them.
