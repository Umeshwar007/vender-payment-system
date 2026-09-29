import asyncio
import random
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Bank simulator")

# Local demo ledger. Repeated successful requests create repeated transfers.
transfers: list["TransferResponse"] = []


class TransferRequest(BaseModel):
    payment_id: UUID
    vendor_id: UUID
    amount_cents: int = Field(gt=0)


class TransferResponse(BaseModel):
    bank_reference: UUID
    payment_id: UUID
    vendor_id: UUID
    amount_cents: int
    status: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"service": "bank-simulator", "status": "ok"}


@app.post("/transfers", response_model=TransferResponse)
async def create_transfer(request: TransferRequest) -> TransferResponse:
    await asyncio.sleep(random.uniform(1, 5))

    # This simulated 500 happens before the transfer is accepted.
    if random.random() < 0.2:
        raise HTTPException(status_code=500, detail="Simulated bank failure")

    transfer = TransferResponse(
        bank_reference=uuid4(),
        payment_id=request.payment_id,
        vendor_id=request.vendor_id,
        amount_cents=request.amount_cents,
        status="accepted",
    )
    transfers.append(transfer)
    return transfer


@app.get("/transfers", response_model=list[TransferResponse])
async def list_transfers() -> list[TransferResponse]:
    return transfers