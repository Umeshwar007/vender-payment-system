from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.invoice_service.app.api.vendors import router as vendors_router
from services.invoice_service.app.db import engine

from services.invoice_service.app.api.invoices import router as invoices_router
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Invoice service", lifespan=lifespan)
app.include_router(vendors_router)
app.include_router(invoices_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"service": "invoice-service", "status": "ok"}