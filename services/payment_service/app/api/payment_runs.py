from uuid import uuid4
import os
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.payment_service.app.db import get_session
from services.payment_service.app.models import (
    InvoiceProjection,
    PaymentOutboxEvent,
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

    


async def load_run_response(
    session: AsyncSession,
    run_id: UUID,
) -> PaymentRunRead:
    run = await session.get(PaymentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Payment run not found")

    payments = list(
        (
            await session.scalars(
                select(Payment)
                .where(Payment.run_id == run_id)
                .order_by(Payment.id)
            )
        ).all()
    )

    return PaymentRunRead(
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


@router.post("/{run_id}/execute", response_model=PaymentRunRead)
async def execute_payment_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> PaymentRunRead:
    bank_url = os.environ.get(
        "BANK_SIMULATOR_URL",
        "http://127.0.0.1:8003",
    )

    payment_calls: list[tuple[UUID, UUID, UUID, int]] = []

    async with session.begin():
        run = await session.scalar(
            select(PaymentRun)
            .where(PaymentRun.id == run_id)
            .with_for_update()
        )
        if run is None:
            raise HTTPException(status_code=404, detail="Payment run not found")

        # Repeated execute requests must never resend completed transfers.
        if run.status in {"completed", "completed_with_errors"}:
            return await load_run_response(session, run_id)

        if run.status != "created":
            raise HTTPException(
                status_code=409,
                detail=f"Payment run cannot execute from status '{run.status}'",
            )

        result = await session.execute(
            select(Payment, InvoiceProjection.vendor_id)
            .join(
                InvoiceProjection,
                InvoiceProjection.invoice_id == Payment.invoice_id,
            )
            .where(Payment.run_id == run_id)
            .order_by(Payment.id)
            .with_for_update(of=Payment)
        )
        rows = result.all()

        if not rows:
            raise HTTPException(status_code=409, detail="Payment run has no payments")

        for payment, vendor_id in rows:
            if payment.status != "queued":
                raise HTTPException(
                    status_code=409,
                    detail="Payment run contains a payment that is not queued",
                )

            # Commit this before contacting the bank. A second request will
            # see the run as executing and cannot send the same payments.
            payment.status = "in_flight"
            payment_calls.append(
                (payment.id, payment.invoice_id, vendor_id, payment.amount_cents)
            )

        run.status = "executing"

    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(base_url=bank_url, timeout=timeout) as client:
        for payment_id, invoice_id, vendor_id, amount_cents in payment_calls:
            outcome = "unknown"
            bank_reference = None

            for attempt in range(3):
                try:
                    response = await client.post(
                        "/transfers",
                        json={
                            "payment_id": str(payment_id),
                            "vendor_id": str(vendor_id),
                            "amount_cents": amount_cents,
                        },
                    )
                except httpx.RequestError:
                    # A timeout or connection failure could happen after
                    # acceptance, so never blindly send this payment again.
                    outcome = "unknown"
                    break

                if response.status_code >= 500:
                    # The supplied simulator raises its 500 before accepting
                    # the transfer, so this specific response is safe to retry.
                    if attempt < 2:
                        continue
                    outcome = "failed"
                    break

                if response.is_error:
                    outcome = "failed"
                    break

                try:
                    body = response.json()
                    if UUID(body["payment_id"]) != payment_id:
                        outcome = "unknown"
                    else:
                        bank_reference = UUID(body["bank_reference"])
                        outcome = "succeeded"
                except (KeyError, TypeError, ValueError):
                    # The bank may have accepted the transfer even if its
                    # response was malformed. Leave it for reconciliation.
                    outcome = "unknown"
                break

            async with session.begin():
                payment = await session.get(
                    Payment,
                    payment_id,
                    with_for_update=True,
                )
                if outcome == "succeeded" and bank_reference is not None:
                    await mark_payment_succeeded(session, payment, bank_reference)
                else:
                    payment.status = outcome
                    payment.bank_reference = bank_reference

    async with session.begin():
        run = await session.get(PaymentRun, run_id, with_for_update=True)
        payment_statuses = list(
            (
                await session.scalars(
                    select(Payment.status).where(Payment.run_id == run_id)
                )
            ).all()
        )

        if any(value in {"unknown", "in_flight"} for value in payment_statuses):
            run.status = "needs_reconciliation"
        elif any(value == "failed" for value in payment_statuses):
            run.status = "completed_with_errors"
        else:
            run.status = "completed"

        run.completed_at = datetime.now(timezone.utc)

    return await load_run_response(session, run_id)


@router.post("/{run_id}/reconcile", response_model=PaymentRunRead)
async def reconcile_payment_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> PaymentRunRead:
    bank_url = os.environ.get(
        "BANK_SIMULATOR_URL",
        "http://127.0.0.1:8003",
    )

    async with session.begin():
        run = await session.scalar(
            select(PaymentRun)
            .where(PaymentRun.id == run_id)
            .with_for_update()
        )
        if run is None:
            raise HTTPException(status_code=404, detail="Payment run not found")

        if run.status == "executing":
            raise HTTPException(
                status_code=409,
                detail="Wait for payment execution to finish before reconciling",
            )

        if run.status != "needs_reconciliation":
            return await load_run_response(session, run_id)

        payment_ids = list(
            (
                await session.scalars(
                    select(Payment.id).where(
                        Payment.run_id == run_id,
                        Payment.status.in_(("unknown", "in_flight")),
                    )
                )
            ).all()
        )

    try:
        async with httpx.AsyncClient(
            base_url=bank_url,
            timeout=httpx.Timeout(10.0),
        ) as client:
            response = await client.get("/transfers")
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not reach the bank ledger; try reconciliation later",
        ) from exc

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail="Bank ledger returned an error",
        )

    try:
        ledger = response.json()
        if not isinstance(ledger, list):
            raise ValueError("Expected a list of transfers")
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Bank ledger returned an invalid response",
        ) from exc

    transfers_by_payment: dict[UUID, list[UUID]] = {}
    for transfer in ledger:
        try:
            payment_id = UUID(transfer["payment_id"])
            bank_reference = UUID(transfer["bank_reference"])
        except (KeyError, TypeError, ValueError):
            continue

        transfers_by_payment.setdefault(payment_id, []).append(bank_reference)

    for payment_id in payment_ids:
        references = transfers_by_payment.get(payment_id, [])

        async with session.begin():
            payment = await session.get(
                Payment,
                payment_id,
                with_for_update=True,
            )
            if payment is None:
                continue

            if len(references) == 1:
                await mark_payment_succeeded(session, payment, references[0])
            else:
                # Zero matches is inconclusive; multiple matches need
                # manual review because the bank may have paid twice.
                payment.status = "unknown"

    async with session.begin():
        run = await session.get(PaymentRun, run_id, with_for_update=True)
        payment_statuses = list(
            (
                await session.scalars(
                    select(Payment.status).where(Payment.run_id == run_id)
                )
            ).all()
        )

        if any(value in {"unknown", "in_flight"} for value in payment_statuses):
            run.status = "needs_reconciliation"
        elif any(value == "failed" for value in payment_statuses):
            run.status = "completed_with_errors"
        else:
            run.status = "completed"

        run.completed_at = datetime.now(timezone.utc)

    return await load_run_response(session, run_id)

async def mark_payment_succeeded(
    session: AsyncSession,
    payment: Payment,
    bank_reference: UUID,
) -> None:
    # This guard makes reconciliation safe to repeat.
    if payment.status not in {"in_flight", "unknown"}:
        return

    projection = await session.get(
        InvoiceProjection,
        payment.invoice_id,
        with_for_update=True,
    )
    if projection is None:
        raise RuntimeError(
            f"Invoice projection {payment.invoice_id} is missing"
        )

    new_amount_paid = projection.amount_paid_cents + payment.amount_cents
    if new_amount_paid > projection.total_cents:
        raise RuntimeError(
            f"Payment would overpay invoice {payment.invoice_id}"
        )

    projection.amount_paid_cents = new_amount_paid
    projection.status = (
        "paid"
        if new_amount_paid == projection.total_cents
        else "partially_paid"
    )
    projection.updated_at = datetime.now(timezone.utc)

    payment.status = "succeeded"
    payment.bank_reference = bank_reference


    session.add(
        PaymentOutboxEvent(
            event_type="payment.succeeded",
            aggregate_id=payment.id,
            payload={
                "schema_version": 1,
                "payment_id": str(payment.id),
                "invoice_id": str(payment.invoice_id),
                "amount_cents": payment.amount_cents,
                "bank_reference": str(bank_reference),
            },
        )
    )