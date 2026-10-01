from fastapi import FastAPI

from services.payment_service.app.api.payment_runs import router as payment_runs_router
from services.payment_service.app.api.reports import router as reports_router

app = FastAPI(title="Payment service")
app.include_router(payment_runs_router)
app.include_router(reports_router)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"service": "payment-service", "status": "ok"}