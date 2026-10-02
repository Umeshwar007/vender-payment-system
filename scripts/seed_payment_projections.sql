\set ON_ERROR_STOP on

BEGIN;

INSERT INTO payment.invoice_projections (
    invoice_id,
    vendor_id,
    invoice_number,
    status,
    due_date,
    total_cents,
    amount_paid_cents
)
SELECT
    md5('perf-invoice-' || n)::uuid,
    '95931eaa-f1fc-4197-b633-5c4d444f324d'::uuid,
    'PERF-' || lpad(n::text, 5, '0'),
    CASE
        WHEN n % 3 = 0 THEN 'partially_paid'
        WHEN n % 3 = 1 THEN 'scheduled'
        ELSE 'approved'
    END,
    CURRENT_DATE - (n % 121)::integer,
    10000 + (n % 900000),
    CASE WHEN n % 3 = 0 THEN (10000 + (n % 900000)) / 4 ELSE 0 END
FROM generate_series(1, 50000) AS series(n)
ON CONFLICT (invoice_id) DO NOTHING;

COMMIT;