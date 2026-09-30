from typing import Annotated,Literal
from datetime import date
from uuid import UUID
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status ,Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.invoice_service.app.db import get_session
from services.invoice_service.app.domain import (
    InvoiceStatus,
    calculate_total_cents,
     InvalidInvoiceTransition,
        transition_invoice,
)
from services.invoice_service.app.models import Invoice, InvoiceLine, Vendor ,OutboxEvent
from services.invoice_service.app.schemas import (
    InvoiceCreate,
    InvoiceDetail,
    InvoicePage,
    InvoiceSummary,
    InvoiceStatusChange,
)







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

@router.get("", response_model=InvoicePage)
async def list_invoices(
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: InvoiceStatus | None = Query(default=None, alias="status"),
    vendor_id: UUID | None = None,
    issued_from: date | None = None,
    issued_to: date | None = None,
    sort_by: Literal[
        "invoice_number",
        "status",
        "issued_date",
        "due_date",
        "total_cents",
        "created_at",
    ] = "issued_date",
    direction: Literal["asc", "desc"] = "desc",
) -> InvoicePage:
    if issued_from and issued_to and issued_from > issued_to:
        raise HTTPException(
            status_code=422,
            detail="issued_from cannot be after issued_to",
        )

    filters = []
    if status_filter is not None:
        filters.append(Invoice.status == status_filter.value)
    if vendor_id is not None:
        filters.append(Invoice.vendor_id == vendor_id)
    if issued_from is not None:
        filters.append(Invoice.issued_date >= issued_from)
    if issued_to is not None:
        filters.append(Invoice.issued_date <= issued_to)

    total = await session.scalar(
        select(func.count(Invoice.id)).where(*filters)
    )

    sort_columns = {
        "invoice_number": Invoice.invoice_number,
        "status": Invoice.status,
        "issued_date": Invoice.issued_date,
        "due_date": Invoice.due_date,
        "total_cents": Invoice.total_cents,
        "created_at": Invoice.created_at,
    }
    sort_column = sort_columns[sort_by]
    order = sort_column.asc() if direction == "asc" else sort_column.desc()

    rows = await session.scalars(
        select(Invoice)
        .where(*filters)
        .order_by(order, Invoice.id.asc())
        .limit(limit)
        .offset(offset)
    )

    return InvoicePage(
        items=list(rows),
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{invoice_id}", response_model=InvoiceDetail)
async def get_invoice(
    invoice_id: UUID,
    session: DbSession,
) -> InvoiceDetail:
    invoice = await session.scalar(
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice_id)
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return InvoiceDetail.model_validate(invoice)


@router.patch("/{invoice_id}/status", response_model=InvoiceDetail)
async def change_invoice_status(
    invoice_id: UUID,
    payload: InvoiceStatusChange,
    session: DbSession,
) -> InvoiceDetail:
    invoice = await session.scalar(
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice_id)
        .with_for_update()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        new_status = transition_invoice(
            InvoiceStatus(invoice.status),
            payload.status,
        )
    except InvalidInvoiceTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    invoice.status = new_status.value

    event_id = uuid4()
    session.add(
        OutboxEvent(
            id=event_id,
            event_type=f"invoice.{new_status.value}",
            aggregate_id=invoice.id,
            payload={
                "event_id": str(event_id),
                "schema_version": 1,
                "invoice_id": str(invoice.id),
                "vendor_id": str(invoice.vendor_id),
                "invoice_number": invoice.invoice_number,
                "status": new_status.value,
                "total_cents": invoice.total_cents,
                "amount_paid_cents": invoice.amount_paid_cents,
                "due_date": invoice.due_date.isoformat(),
            },
        )
    )

    await session.commit()

    updated_invoice = await session.scalar(
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice_id)
    )
    assert updated_invoice is not None
    return InvoiceDetail.model_validate(updated_invoice)