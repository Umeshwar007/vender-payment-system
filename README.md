
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

## Run locally on Windows

### 1. Install dependencies and start infrastructure

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d db redis


 ### 2. Apply database migrations

$env:INVOICE_DATABASE_URL = "postgresql+asyncpg://invoice_user:local_invoice_password@127.0.0.1:5433/invoicing"
python -m alembic -c services\invoice_service\alembic.ini upgrade head

$env:PAYMENT_DATABASE_URL = "postgresql+asyncpg://payment_user:local_payment_password@127.0.0.1:5433/invoicing"
python -m alembic -c services\payment_service\alembic.ini upgrade head


  ### 3. Start the services
Run each command in a separate PowerShell terminal from the repository root.
Invoice API:
$env:INVOICE_DATABASE_URL = "postgresql+asyncpg://invoice_user:local_invoice_password@127.0.0.1:5433/invoicing"
python -m uvicorn services.invoice_service.app.main:app --reload --port 8001


  ### 4. Invoice outbox worker:
$env:INVOICE_DATABASE_URL = "postgresql+asyncpg://invoice_user:local_invoice_password@127.0.0.1:5433/invoicing"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
python -m services.invoice_service.app.outbox_worker


  ### 5. Payment API:
$env:PAYMENT_DATABASE_URL = "postgresql+asyncpg://payment_user:local_payment_password@127.0.0.1:5433/invoicing"
python -m uvicorn services.payment_service.app.main:app --reload --port 8002


   ### 6. Payment event consumer:
$env:PAYMENT_DATABASE_URL = "postgresql+asyncpg://payment_user:local_payment_password@127.0.0.1:5433/invoicing"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
python -m services.payment_service.app.event_consumer


  ### 7. Bank simulator:
python -m uvicorn services.bank_simulator.app.main:app --reload --port 8003


  ### 8. Frontend, in another terminal:
Set-Location frontend
npm install
npm run dev



   ### 9.  Seed performance data
After applying migrations, run the SQL seed files from the repository root:
docker compose cp .\scripts\seed_performance_data.sql db:/tmp/seed_performance_data.sql
docker compose exec db psql -U invoice_user -d invoicing -v ON_ERROR_STOP=1 -f /tmp/seed_performance_data.sql

docker compose cp .\scripts\seed_payment_projections.sql db:/tmp/seed_payment_projections.sql
docker compose exec db psql -U payment_user -d invoicing -v ON_ERROR_STOP=1 -f /tmp/seed_payment_projections.sql



   ###  10. Run backend tests
Start the database and apply migrations first. Then, from the repository root:
$env:PAYMENT_DATABASE_URL = "postgresql+asyncpg://payment_user:local_payment_password@127.0.0.1:5433/invoicing"
.\.venv\Scripts\python.exe -m pytest services\invoice_service\tests services\payment_service\tests



   ### 11. Check the frontend
From the frontend directory:
npm run build
npm run lint