from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.payment_service.app.db import get_session
from services.payment_service.app.models import (
    InvoiceProjection,
    Payment,
    PaymentRun,
)
from services.payment_service.app.schemas import (
    PaymentRead,
    PaymentRunCreate,
    PaymentRunRead,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment-runs", tags=["payment-runs"])

ACTIVE_PAYMENT_STATUSES = ("queued", "in_flight", "unknown")


@router.post(
    "",
    response_model=PaymentRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_run(
    request: PaymentRunCreate,
    session: AsyncSession = Depends(get_session),
) -> PaymentRunRead:
    try:
        async with session.begin():
            projections_result = await session.scalars(
                select(InvoiceProjection)
                .where(InvoiceProjection.invoice_id.in_(request.invoice_ids))
                .order_by(InvoiceProjection.invoice_id)
                .with_for_update()
            )
            projections = list(projections_result)

            if len(projections) != len(request.invoice_ids):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="One or more invoices were not found",
                )

            if any(projection.status != "scheduled" for projection in projections):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only scheduled invoices can be added to a payment run",
                )

            existing_payment_result = await session.scalars(
                select(Payment.invoice_id).where(
                    Payment.invoice_id.in_(request.invoice_ids),
                    Payment.status.in_(ACTIVE_PAYMENT_STATUSES),
                )
            )
            if existing_payment_result.first() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="One or more invoices already have an active payment",
                )

            amounts = {
                projection.invoice_id: (
                    projection.total_cents - projection.amount_paid_cents
                )
                for projection in projections
            }

            if any(amount <= 0 for amount in amounts.values()):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="One or more invoices have no remaining balance",
                )

            run = PaymentRun(
                id=uuid4(),
                status="created",
                total_cents=sum(amounts.values()),
            )
            session.add(run)
            await session.flush()  # Save the run first so each payment's run_id has a parent.
            payments = [
                Payment(
                    id=uuid4(),
                    run_id=run.id,
                    invoice_id=projection.invoice_id,
                    amount_cents=amounts[projection.invoice_id],
                    idempotency_key=str(uuid4()),
                    status="queued",
                )
                for projection in projections
            ]
            session.add_all(payments)

            await session.flush()
            await session.refresh(run)

            response = PaymentRunRead(
                id=run.id,
                status=run.status,
                total_cents=run.total_cents,
                created_at=run.created_at,
                completed_at=run.completed_at,
                payments=[
                    PaymentRead(
                        id=payment.id,
                        invoice_id=payment.invoice_id,
                        amount_cents=payment.amount_cents,
                        status=payment.status,
                        bank_reference=payment.bank_reference,
                    )
                    for payment in payments
                ],
            )

        return response

    except IntegrityError as exc:
        logger.exception("Database integrity error while creating payment run")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invoice already has an active payment",
        ) from exc