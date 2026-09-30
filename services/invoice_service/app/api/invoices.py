from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.invoice_service.app.db import get_session
from services.invoice_service.app.domain import (
    InvoiceStatus,
    calculate_total_cents,
)
from services.invoice_service.app.models import Invoice, InvoiceLine, Vendor
from services.invoice_service.app.schemas import InvoiceCreate, InvoiceDetail

router = APIRouter(prefix="/invoices", tags=["invoices"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=InvoiceDetail, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    session: DbSession,
) -> InvoiceDetail:
    vendor = await session.get(Vendor, payload.vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if not vendor.is_active:
        raise HTTPException(status_code=409, detail="Vendor is inactive")

    line_amounts = [
        (line.quantity, line.unit_price_cents)
        for line in payload.lines
    ]
    invoice_total = calculate_total_cents(line_amounts)

    invoice = Invoice(
        vendor_id=payload.vendor_id,
        invoice_number=payload.invoice_number,
        status=InvoiceStatus.DRAFT.value,
        issued_date=payload.issued_date,
        due_date=payload.due_date,
        total_cents=invoice_total,
        amount_paid_cents=0,
        lines=[
            InvoiceLine(
                description=line.description,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
            )
            for line in payload.lines
        ],
    )
    session.add(invoice)

    try:
        await session.flush()
        invoice_id = invoice.id
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="An invoice with this number already exists for the vendor",
        ) from None

    saved_invoice = await session.scalar(
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice_id)
    )
    assert saved_invoice is not None
    return InvoiceDetail.model_validate(saved_invoice)