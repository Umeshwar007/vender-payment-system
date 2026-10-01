import asyncio
from datetime import date
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select

from services.payment_service.app.api.payment_runs import (
    create_payment_run,
    execute_payment_run,
    mark_payment_succeeded,
)
from services.payment_service.app.db import  SessionFactory, engine
from services.payment_service.app.models import (
    InvoiceProjection,
    Payment,
    PaymentRun,
)
from services.payment_service.app.schemas import PaymentRunCreate, PaymentRunRead

async def _run_test_and_dispose(coroutine):
    try:
        await coroutine
    finally:
        await engine.dispose()
def test_concurrent_runs_cannot_schedule_the_same_invoice_twice() -> None:
    asyncio.run(
        _run_test_and_dispose(_exercise_concurrent_run_creation())
    )

async def _exercise_concurrent_run_creation() -> None:
    invoice_id = uuid4()
    run_ids = []

    try:
        async with SessionFactory.begin() as session:
            session.add(
                InvoiceProjection(
                    invoice_id=invoice_id,
                    vendor_id=uuid4(),
                    invoice_number=f"TEST-{invoice_id}",
                    status="scheduled",
                    due_date=date.today(),
                    total_cents=5000,
                    amount_paid_cents=0,
                )
            )

        async def create_run():
            async with SessionFactory() as session:
                try:
                    return await create_payment_run(
                        PaymentRunCreate(invoice_ids=[invoice_id]),
                        session,
                    )
                except HTTPException as exc:
                    return exc

        results = await asyncio.gather(create_run(), create_run())

        successful_runs = [
            result for result in results if isinstance(result, PaymentRunRead)
        ]
        conflicts = [
            result
            for result in results
            if isinstance(result, HTTPException) and result.status_code == 409
        ]

        assert len(successful_runs) == 1
        assert len(conflicts) == 1

        async with SessionFactory() as session:
            payments = list(
                (
                    await session.scalars(
                        select(Payment).where(Payment.invoice_id == invoice_id)
                    )
                ).all()
            )

        assert len(payments) == 1
        run_ids.append(successful_runs[0].id)

        # A repeated execute request for a completed run must return its result,
        # without submitting the payment to the bank a second time.
        async with SessionFactory.begin() as session:
            run = await session.get(PaymentRun, successful_runs[0].id)
            payment = await session.scalar(
                select(Payment).where(Payment.invoice_id == invoice_id)
            )
            run.status = "completed"
            payment.status = "succeeded"
            payment.bank_reference = uuid4()

        async with SessionFactory() as session:
            response = await execute_payment_run(successful_runs[0].id, session)

        assert response.status == "completed"
        assert len(response.payments) == 1
        assert response.payments[0].status == "succeeded"

    finally:
        async with SessionFactory.begin() as session:
            run_ids = list(
                (
                    await session.scalars(
                        select(Payment.run_id).where(
                            Payment.invoice_id == invoice_id
                        )
                    )
                ).all()
            )

            await session.execute(
                delete(Payment).where(Payment.invoice_id == invoice_id)
            )

            if run_ids:
                await session.execute(
                    delete(PaymentRun).where(PaymentRun.id.in_(run_ids))
                )

            await session.execute(
                delete(InvoiceProjection).where(
                    InvoiceProjection.invoice_id == invoice_id
                )
            )


def test_successful_payment_updates_projection_only_once() -> None:
    asyncio.run(
        _run_test_and_dispose(_exercise_successful_payment_update())
    )

async def _exercise_successful_payment_update() -> None:
    invoice_id = uuid4()
    run_id = uuid4()
    payment_id = uuid4()
    bank_reference = uuid4()

    try:
        async with SessionFactory.begin() as session:
            session.add(
                InvoiceProjection(
                    invoice_id=invoice_id,
                    vendor_id=uuid4(),
                    invoice_number=f"TEST-{invoice_id}",
                    status="scheduled",
                    due_date=date.today(),
                    total_cents=5000,
                    amount_paid_cents=0,
                )
            )
            session.add(
                PaymentRun(
                    id=run_id,
                    status="executing",
                    total_cents=5000,
                )
            )
            await session.flush()

            session.add(
                Payment(
                    id=payment_id,
                    run_id=run_id,
                    invoice_id=invoice_id,
                    amount_cents=5000,
                    idempotency_key=f"test-{payment_id}",
                    status="in_flight",
                )
            )

        # Apply a confirmed bank result.
        async with SessionFactory.begin() as session:
            payment = await session.get(
                Payment,
                payment_id,
                with_for_update=True,
            )
            await mark_payment_succeeded(session, payment, bank_reference)

        # Simulate receiving the same reconciliation result again.
        async with SessionFactory.begin() as session:
            payment = await session.get(
                Payment,
                payment_id,
                with_for_update=True,
            )
            await mark_payment_succeeded(session, payment, bank_reference)

        async with SessionFactory() as session:
            projection = await session.get(InvoiceProjection, invoice_id)
            payment = await session.get(Payment, payment_id)

        assert projection.amount_paid_cents == 5000
        assert projection.status == "paid"
        assert payment.status == "succeeded"
        assert payment.bank_reference == bank_reference

    finally:
        async with SessionFactory.begin() as session:
            await session.execute(
                delete(Payment).where(Payment.invoice_id == invoice_id)
            )
            await session.execute(
                delete(PaymentRun).where(PaymentRun.id == run_id)
            )
            await session.execute(
                delete(InvoiceProjection).where(
                    InvoiceProjection.invoice_id == invoice_id
                )
            )