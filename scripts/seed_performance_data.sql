\set ON_ERROR_STOP on

BEGIN;

-- Add 49,999 invoices. Together with your existing invoice, this makes 50,000.
INSERT INTO invoice.vendors (id, name, email, is_active)
VALUES (
    '95931eaa-f1fc-4197-b633-5c4d444f324d'::uuid,
    'Performance seed vendor',
    'performance-seed@example.test',
    true
)
ON CONFLICT (id) DO NOTHING;
INSERT INTO invoice.invoices (
    id,
    vendor_id,
    invoice_number,
    status,
    issued_date,
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
    CURRENT_DATE - (180 + (n % 121))::integer,
    CURRENT_DATE - (n % 121)::integer,
    10000 + (n % 900000),
    CASE WHEN n % 3 = 0 THEN (10000 + (n % 900000)) / 4 ELSE 0 END
FROM generate_series(1, 49999) AS series(n)
ON CONFLICT (vendor_id, invoice_number) DO NOTHING;

-- Add one matching line per seeded invoice.
INSERT INTO invoice.invoice_lines (
    id,
    invoice_id,
    description,
    quantity,
    unit_price_cents
)
SELECT
    md5('perf-line-' || n)::uuid,
    md5('perf-invoice-' || n)::uuid,
    'Performance seed item',
    1,
    10000 + (n % 900000)
FROM generate_series(1, 50000) AS series(n)
ON CONFLICT (id) DO NOTHING;

COMMIT;