
# Vendor Payment System

A small accounts-payable platform for managing vendors and invoices, scheduling payment runs, simulating bank transfers, and reporting outstanding balances.

## Features

- Vendor creation, editing, activation/deactivation, and deletion.
- Invoice creation with line items, draft editing/deletion, status transitions, and pagination/filtering.
- Transactional invoice outbox delivered through Redis Streams to the payment service.
- Payment projections, payment runs, bank execution, and reconciliation for unknown outcomes.
- Aging report with as-of date, vendor filter, bucket ordering, summary totals, and pagination.
- React frontend for vendors, invoices, payment runs, and aging reports.

## Architecture

The application has three backend processes and a React frontend:

- **Invoice service** owns vendors, invoices, invoice lines, and invoice outbox events in the `invoice` schema.
- **Payment service** owns payment runs, payments, processed-event records, and invoice projections in the `payment` schema.
- **Bank simulator** represents an external bank and provides a transfer ledger.
- **Frontend** calls the APIs through the Vite development proxy.

When an invoice status changes, the invoice service records the change and an outbox event in one database transaction. The outbox worker publishes events to Redis Streams. The payment consumer applies events to its local projection and records event IDs to skip duplicate deliveries.

The aging report is calculated by a single SQL query against the payment service’s invoice projection.

See [DECISIONS.md](DECISIONS.md) for design and retry decisions, and [PERFORMANCE.md](PERFORMANCE.md) for the aging-report baseline.

## Technology

- Python, FastAPI, Pydantic, SQLAlchemy async, Alembic
- PostgreSQL 16
- Redis Streams
- React, TypeScript, Vite, TanStack Query
- Docker Compose for PostgreSQL and Redis

## Requirements

- Python and Node.js installed
- Docker Desktop with Docker Compose
- PowerShell on Windows, or equivalent shell commands for another OS

## Run locally on Windows

Run the commands from the repository root unless a step says otherwise.

### 1. Install Python dependencies and start infrastructure

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d db redis
```

Compose starts PostgreSQL on port `5433` and Redis on port `6379`. The PostgreSQL initialization script creates the `invoice_user` and `payment_user` roles and their schemas.

### 2. Apply database migrations

```powershell
$env:INVOICE_DATABASE_URL = "postgresql+asyncpg://invoice_user:local_invoice_password@127.0.0.1:5433/invoicing"
python -m alembic -c services\invoice_service\alembic.ini upgrade head

$env:PAYMENT_DATABASE_URL = "postgresql+asyncpg://payment_user:local_payment_password@127.0.0.1:5433/invoicing"
python -m alembic -c services\payment_service\alembic.ini upgrade head
```

### 3. Seed performance data

After applying migrations, run these commands from the repository root:

```powershell
docker compose cp .\scripts\seed_performance_data.sql db:/tmp/seed_performance_data.sql
docker compose exec db psql -U invoice_user -d invoicing -v ON_ERROR_STOP=1 -f /tmp/seed_performance_data.sql

docker compose cp .\scripts\seed_payment_projections.sql db:/tmp/seed_payment_projections.sql
docker compose exec db psql -U payment_user -d invoicing -v ON_ERROR_STOP=1 -f /tmp/seed_payment_projections.sql
```

The scripts create deterministic sample records for the invoice service and matching payment projections. They can be rerun without duplicating those seed records.

### 4. Start the services

Start each process in its own PowerShell terminal from the repository root. Keep the terminals open.

**Invoice API — port 8001**

```powershell
$env:INVOICE_DATABASE_URL = "postgresql+asyncpg://invoice_user:local_invoice_password@127.0.0.1:5433/invoicing"
python -m uvicorn services.invoice_service.app.main:app --reload --port 8001
```

**Invoice outbox worker**

```powershell
$env:INVOICE_DATABASE_URL = "postgresql+asyncpg://invoice_user:local_invoice_password@127.0.0.1:5433/invoicing"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
python -m services.invoice_service.app.outbox_worker
```

**Payment API — port 8002**

```powershell
$env:PAYMENT_DATABASE_URL = "postgresql+asyncpg://payment_user:local_payment_password@127.0.0.1:5433/invoicing"
python -m uvicorn services.payment_service.app.main:app --reload --port 8002
```

**Payment event consumer**

```powershell
$env:PAYMENT_DATABASE_URL = "postgresql+asyncpg://payment_user:local_payment_password@127.0.0.1:5433/invoicing"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
python -m services.payment_service.app.event_consumer
```

**Bank simulator — port 8003**

```powershell
python -m uvicorn services.bank_simulator.app.main:app --reload --port 8003
```

**Frontend — port 5173**

Open another terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal, usually `http://localhost:5173`.

### 5. API documentation

FastAPI Swagger pages are available while each API is running:

- Invoice service: `http://localhost:8001/docs`
- Payment service: `http://localhost:8002/docs`
- Bank simulator: `http://localhost:8003/docs`

## API overview

| Service | Method and path | Purpose |
|---|---|---|
| Invoice | `GET /health` | Health check |
| Invoice | `/vendors` | Create and list vendors |
| Invoice | `/vendors/{vendor_id}` | Read, replace, or delete a vendor |
| Invoice | `/invoices` | Create and list invoices; list supports pagination and status filtering |
| Invoice | `/invoices/{invoice_id}` | Read, replace a draft, or delete a draft invoice |
| Invoice | `PATCH /invoices/{invoice_id}/status` | Change invoice status |
| Payment | `GET /health` | Health check |
| Payment | `POST /payment-runs` | Create a payment run |
| Payment | `POST /payment-runs/{run_id}/execute` | Execute a payment run |
| Payment | `POST /payment-runs/{run_id}/reconcile` | Reconcile unknown payment outcomes |
| Payment | `GET /reports/aging` | Get the aging report |
| Bank | `GET /health` | Health check |
| Bank | `POST /transfers` | Simulate a bank transfer |
| Bank | `GET /transfers` | View the simulator transfer ledger |

For request and response schemas, use the Swagger pages.

## Payment safety

The payment service stores payment attempts and prevents concurrent runs from reserving the same invoice. A bank simulator failure that is known to occur before acceptance can be retried. If the request outcome is ambiguous, the payment is marked `unknown` and reconciled against the bank ledger instead of being blindly resubmitted.

The simulator keeps its ledger in memory. Restarting it clears that ledger, so it does not model durable bank-side reconciliation.

## Run backend tests

Start Docker and apply the database migrations first. From the repository root:

```powershell
$env:PAYMENT_DATABASE_URL = "postgresql+asyncpg://payment_user:local_payment_password@127.0.0.1:5433/invoicing"
.\.venv\Scripts\python.exe -m pytest services\invoice_service\tests services\payment_service\tests -q
```

## Check the frontend

From the `frontend` directory:

```powershell
npm run build
npm run lint
```

## Project structure

```text
services/
  bank_simulator/       Simulated external bank API
  invoice_service/      Vendor and invoice API, migrations, tests, outbox worker
  payment_service/      Payment API, migrations, tests, event consumer, reports
frontend/               React and TypeScript application
infra/postgres/init/    PostgreSQL role and schema initialization
scripts/                Repeatable performance data seed SQL
DECISIONS.md            Architecture and reliability decisions
PERFORMANCE.md          Aging report performance baseline
compose.yaml            PostgreSQL and Redis development infrastructure
```

The credentials shown in these local development commands are the sample values from `.env.example`.
