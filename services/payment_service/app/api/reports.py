from datetime import date
from math import ceil
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.payment_service.app.db import get_session
from services.payment_service.app.schemas import (
    AgingBucketSummary,
    AgingInvoiceRead,
    AgingReportRead,
)


router = APIRouter(prefix="/reports", tags=["reports"])

AGING_SQL = text(
    """
    WITH base AS (
        SELECT
            invoice_id,
            vendor_id,
            invoice_number,
            due_date,
            total_cents - amount_paid_cents AS outstanding_cents,
            GREATEST(CAST(:as_of AS date) - due_date, 0) AS days_past_due,
            CASE
                WHEN due_date >= CAST(:as_of AS date) THEN 0
                WHEN CAST(:as_of AS date) - due_date <= 30 THEN 1
                WHEN CAST(:as_of AS date) - due_date <= 60 THEN 2
                WHEN CAST(:as_of AS date) - due_date <= 90 THEN 3
                ELSE 4
            END AS bucket_rank
        FROM payment.invoice_projections
        WHERE status IN ('approved', 'scheduled', 'partially_paid')
          AND amount_paid_cents < total_cents
          AND (
    CAST(:vendor_id AS uuid) IS NULL
    OR vendor_id = CAST(:vendor_id AS uuid)
)
    ),
    summary AS (
        SELECT
            COUNT(*)::int AS total_count,

            COUNT(*) FILTER (WHERE bucket_rank = 0)::int AS current_count,
            COALESCE(
                SUM(outstanding_cents) FILTER (WHERE bucket_rank = 0), 0
            )::bigint AS current_amount,

            COUNT(*) FILTER (WHERE bucket_rank = 1)::int AS days_1_30_count,
            COALESCE(
                SUM(outstanding_cents) FILTER (WHERE bucket_rank = 1), 0
            )::bigint AS days_1_30_amount,

            COUNT(*) FILTER (WHERE bucket_rank = 2)::int AS days_31_60_count,
            COALESCE(
                SUM(outstanding_cents) FILTER (WHERE bucket_rank = 2), 0
            )::bigint AS days_31_60_amount,

            COUNT(*) FILTER (WHERE bucket_rank = 3)::int AS days_61_90_count,
            COALESCE(
                SUM(outstanding_cents) FILTER (WHERE bucket_rank = 3), 0
            )::bigint AS days_61_90_amount,

            COUNT(*) FILTER (WHERE bucket_rank = 4)::int AS over_90_count,
            COALESCE(
                SUM(outstanding_cents) FILTER (WHERE bucket_rank = 4), 0
            )::bigint AS over_90_amount
        FROM base
    ),
    ranked AS (
        SELECT
            base.*,
            ROW_NUMBER() OVER (
                ORDER BY
                    CASE
                        WHEN :bucket_order = 'desc' THEN -bucket_rank
                        ELSE bucket_rank
                    END,
                    due_date,
                    invoice_id
            ) AS page_row_number
        FROM base
    ),
    page_rows AS (
        SELECT *
        FROM ranked
        WHERE page_row_number > :offset
          AND page_row_number <= :offset + :page_size
    )
    SELECT
        summary.*,
        page_rows.invoice_id,
        page_rows.vendor_id,
        page_rows.invoice_number,
        page_rows.due_date,
        page_rows.outstanding_cents,
        page_rows.days_past_due,
        page_rows.bucket_rank,
        page_rows.page_row_number
    FROM summary
    LEFT JOIN page_rows ON TRUE
    ORDER BY page_rows.page_row_number
    """
)


@router.get("/aging", response_model=AgingReportRead)
async def get_aging_report(
    as_of: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    bucket_order: Literal["asc", "desc"] = "asc",
    session: AsyncSession = Depends(get_session),
    vendor_id: UUID | None = None,
) -> AgingReportRead:
    report_date = as_of or date.today()
    offset = (page - 1) * page_size

    result = await session.execute(
        AGING_SQL,
        {
            "as_of": report_date,
            "bucket_order": bucket_order,
            "offset": offset,
            "page_size": page_size,
            "vendor_id": vendor_id,
        },
    )
    rows = result.mappings().all()
    summary = rows[0]

    buckets = {
        "current": AgingBucketSummary(
            invoice_count=summary["current_count"],
            amount_cents=summary["current_amount"],
        ),
        "1-30": AgingBucketSummary(
            invoice_count=summary["days_1_30_count"],
            amount_cents=summary["days_1_30_amount"],
        ),
        "31-60": AgingBucketSummary(
            invoice_count=summary["days_31_60_count"],
            amount_cents=summary["days_31_60_amount"],
        ),
        "61-90": AgingBucketSummary(
            invoice_count=summary["days_61_90_count"],
            amount_cents=summary["days_61_90_amount"],
        ),
        "over-90": AgingBucketSummary(
            invoice_count=summary["over_90_count"],
            amount_cents=summary["over_90_amount"],
        ),
    }

    bucket_names = {
        0: "current",
        1: "1-30",
        2: "31-60",
        3: "61-90",
        4: "over-90",
    }

    invoices = [
        AgingInvoiceRead(
            invoice_id=row["invoice_id"],
            vendor_id=row["vendor_id"],
            invoice_number=row["invoice_number"],
            due_date=row["due_date"],
            outstanding_cents=row["outstanding_cents"],
            days_past_due=row["days_past_due"],
            bucket=bucket_names[row["bucket_rank"]],
        )
        for row in rows
        if row["invoice_id"] is not None
    ]

    total_count = summary["total_count"]

    return AgingReportRead(
        as_of=report_date,
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=ceil(total_count / page_size) if total_count else 0,
        buckets=buckets,
        invoices=invoices,
    )
