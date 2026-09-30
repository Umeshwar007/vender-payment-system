from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    # Payment tables are separate from invoice-service tables.
    metadata = MetaData(schema="payment")


class InvoiceProjection(Base):
    __tablename__ = "invoice_projections"
    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('draft', 'approved', 'scheduled', 'partially_paid', 'paid', 'void')",
            name="ck_projection_invoice_status",
        ),
        CheckConstraint(
            "total_cents >= 0 AND amount_paid_cents >= 0 "
            "AND amount_paid_cents <= total_cents",
            name="ck_projection_not_overpaid",
        ),
        Index("ix_projection_status_due_date", "status", "due_date"),
    )

    invoice_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    vendor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    due_date: Mapped[Date] = mapped_column(Date, nullable=False)
    total_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_paid_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    # The source event ID is the primary key, so it can be applied only once.
    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PaymentRun(Base):
    __tablename__ = "payment_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('created', 'executing', 'completed', "
            "'completed_with_errors', 'needs_reconciliation')",
            name="ck_payment_run_status",
        ),
        CheckConstraint("total_cents >= 0", name="ck_payment_run_total_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="created"
    )
    total_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("run_id", "invoice_id", name="uq_payment_run_invoice"),
        CheckConstraint("amount_cents > 0", name="ck_payment_amount_positive"),
        CheckConstraint(
            "status IN ('queued', 'in_flight', 'succeeded', 'failed', 'unknown')",
            name="ck_payment_status",
        ),
        # An invoice can have only one active payment attempt at a time.
        Index(
            "uq_payment_active_invoice",
            "invoice_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'in_flight', 'unknown')"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("payment_runs.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoice_projections.invoice_id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )
    bank_reference: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )