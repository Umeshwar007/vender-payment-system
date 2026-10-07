from datetime import date
from math import ceil
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.payment_service.app.db import get_session
from services.payment_service.app.schemas import (
    AgingReportRead,
    VendorAgingRead,
)


router = APIRouter(prefix="/reports", tags=["reports"])


AGING_SQL = text(
    """
    WITH invoice_balances AS (
        SELECT
            vendor_id,
            total_cents - amount_paid_cents AS outstanding_cents,
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
    ),
    vendor_totals AS (
        SELECT
            vendor_id,
            COALESCE(SUM(outstanding_cents)
                FILTER (WHERE bucket_rank = 0), 0)::bigint AS current_cents,
            COALESCE(SUM(outstanding_cents)
                FILTER (WHERE bucket_rank = 1), 0)::bigint AS days_1_30_cents,
            COALESCE(SUM(outstanding_cents)
                FILTER (WHERE bucket_rank = 2), 0)::bigint AS days_31_60_cents,
            COALESCE(SUM(outstanding_cents)
                FILTER (WHERE bucket_rank = 3), 0)::bigint AS days_61_90_cents,
            COALESCE(SUM(outstanding_cents)
                FILTER (WHERE bucket_rank = 4), 0)::bigint AS days_90_plus_cents,
            SUM(outstanding_cents)::bigint AS total_outstanding_cents
        FROM invoice_balances
        GROUP BY vendor_id
    ),
    ranked AS (
        SELECT
            vendor_totals.*,
            RANK() OVER (
                ORDER BY total_outstanding_cents DESC
            ) AS vendor_rank,
            ROUND(
                100.0 * total_outstanding_cents
                / NULLIF(SUM(total_outstanding_cents) OVER (), 0),
                2
            ) AS share_pct
        FROM vendor_totals
    ),
    filtered AS (
        SELECT
            ranked.*,
            COUNT(*) OVER ()::int AS total_count
        FROM ranked
        WHERE CAST(:vendor_id AS uuid) IS NULL
           OR vendor_id = CAST(:vendor_id AS uuid)
    ),
    metadata AS (
        SELECT COUNT(*)::int AS total_count
        FROM filtered
    ),
    page_rows AS (
        SELECT *
        FROM filtered
        ORDER BY
            CASE WHEN :sort_by = 'total' AND :sort_order = 'asc'
                THEN total_outstanding_cents END ASC,
            CASE WHEN :sort_by = 'total' AND :sort_order = 'desc'
                THEN total_outstanding_cents END DESC,
            CASE WHEN :sort_by = 'current' AND :sort_order = 'asc'
                THEN current_cents END ASC,
            CASE WHEN :sort_by = 'current' AND :sort_order = 'desc'
                THEN current_cents END DESC,
            CASE WHEN :sort_by = 'days_1_30' AND :sort_order = 'asc'
                THEN days_1_30_cents END ASC,
            CASE WHEN :sort_by = 'days_1_30' AND :sort_order = 'desc'
                THEN days_1_30_cents END DESC,
            CASE WHEN :sort_by = 'days_31_60' AND :sort_order = 'asc'
                THEN days_31_60_cents END ASC,
            CASE WHEN :sort_by = 'days_31_60' AND :sort_order = 'desc'
                THEN days_31_60_cents END DESC,
            CASE WHEN :sort_by = 'days_61_90' AND :sort_order = 'asc'
                THEN days_61_90_cents END ASC,
            CASE WHEN :sort_by = 'days_61_90' AND :sort_order = 'desc'
                THEN days_61_90_cents END DESC,
            CASE WHEN :sort_by = 'days_90_plus' AND :sort_order = 'asc'
                THEN days_90_plus_cents END ASC,
            CASE WHEN :sort_by = 'days_90_plus' AND :sort_order = 'desc'
                THEN days_90_plus_cents END DESC,
            vendor_id ASC
        LIMIT :page_size OFFSET :offset
    )
    SELECT
        metadata.total_count,
        page_rows.vendor_id,
        page_rows.current_cents,
        page_rows.days_1_30_cents,
        page_rows.days_31_60_cents,
        page_rows.days_61_90_cents,
        page_rows.days_90_plus_cents,
        page_rows.total_outstanding_cents,
        page_rows.vendor_rank,
        page_rows.share_pct
    FROM metadata
    LEFT JOIN page_rows ON TRUE
    ORDER BY
        CASE WHEN :sort_by = 'total' AND :sort_order = 'asc'
            THEN page_rows.total_outstanding_cents END ASC,
        CASE WHEN :sort_by = 'total' AND :sort_order = 'desc'
            THEN page_rows.total_outstanding_cents END DESC,
        CASE WHEN :sort_by = 'current' AND :sort_order = 'asc'
            THEN page_rows.current_cents END ASC,
        CASE WHEN :sort_by = 'current' AND :sort_order = 'desc'
            THEN page_rows.current_cents END DESC,
        CASE WHEN :sort_by = 'days_1_30' AND :sort_order = 'asc'
            THEN page_rows.days_1_30_cents END ASC,
        CASE WHEN :sort_by = 'days_1_30' AND :sort_order = 'desc'
            THEN page_rows.days_1_30_cents END DESC,
        CASE WHEN :sort_by = 'days_31_60' AND :sort_order = 'asc'
            THEN page_rows.days_31_60_cents END ASC,
        CASE WHEN :sort_by = 'days_31_60' AND :sort_order = 'desc'
            THEN page_rows.days_31_60_cents END DESC,
        CASE WHEN :sort_by = 'days_61_90' AND :sort_order = 'asc'
            THEN page_rows.days_61_90_cents END ASC,
        CASE WHEN :sort_by = 'days_61_90' AND :sort_order = 'desc'
            THEN page_rows.days_61_90_cents END DESC,
        CASE WHEN :sort_by = 'days_90_plus' AND :sort_order = 'asc'
            THEN page_rows.days_90_plus_cents END ASC,
        CASE WHEN :sort_by = 'days_90_plus' AND :sort_order = 'desc'
            THEN page_rows.days_90_plus_cents END DESC,
        page_rows.vendor_id ASC
    """
)


@router.get("/aging", response_model=AgingReportRead)
async def get_aging_report(
    as_of: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: Literal[
        "total",
        "current",
        "days_1_30",
        "days_31_60",
        "days_61_90",
        "days_90_plus",
    ] = "total",
    sort_order: Literal["asc", "desc"] = "desc",
    vendor_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> AgingReportRead:
    report_date = as_of or date.today()
    offset = (page - 1) * page_size

    result = await session.execute(
        AGING_SQL,
        {
            "as_of": report_date,
            "offset": offset,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "vendor_id": vendor_id,
        },
    )
    rows = result.mappings().all()
    total_count = rows[0]["total_count"]

    vendors = [
        VendorAgingRead(
            vendor_id=row["vendor_id"],
            current_cents=row["current_cents"],
            days_1_30_cents=row["days_1_30_cents"],
            days_31_60_cents=row["days_31_60_cents"],
            days_61_90_cents=row["days_61_90_cents"],
            days_90_plus_cents=row["days_90_plus_cents"],
            total_outstanding_cents=row["total_outstanding_cents"],
            vendor_rank=row["vendor_rank"],
            share_pct=row["share_pct"],
        )
        for row in rows
        if row["vendor_id"] is not None
    ]

    return AgingReportRead(
        as_of=report_date,
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=ceil(total_count / page_size) if total_count else 0,
        vendors=vendors,
    )