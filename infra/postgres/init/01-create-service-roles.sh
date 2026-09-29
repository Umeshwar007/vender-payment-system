#!/usr/bin/env bash
set -e

psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=invoice_password="$INVOICE_DB_PASSWORD" \
  --set=payment_password="$PAYMENT_DB_PASSWORD" <<'SQL'
CREATE ROLE invoice_user LOGIN PASSWORD :'invoice_password';
CREATE ROLE payment_user LOGIN PASSWORD :'payment_password';

CREATE SCHEMA invoice AUTHORIZATION invoice_user;
CREATE SCHEMA payment AUTHORIZATION payment_user;
SQL