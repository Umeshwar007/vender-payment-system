# Performance

## Aging report baseline

Measured on 2026-10-02 against the local development environment.

| Item | Result |
|---|---:|
| Database | PostgreSQL 16 in Docker Desktop |
| Invoices | 50,000 |
| Invoice lines | 50,000 |
| Payment projections | 50,000 |
| Endpoint | `GET /reports/aging` |
| Page size | 20 |
| Requests measured | 20 |
| Warm-up requests | 2, excluded |
| Median response time | 220.86 ms |
| P95 response time | 686.35 ms |

The requests were run sequentially from PowerShell against the payment API at `127.0.0.1:8002`. Timing measures the full HTTP request and response, including application and local network overhead. This is a local baseline, not a concurrent-load test; results can vary with machine load and environment.

To reproduce, start the payment API and run the PowerShell benchmark command recorded for this measurement. Confirm that each response returns 20 invoice rows and reports a total count of 50,000.
