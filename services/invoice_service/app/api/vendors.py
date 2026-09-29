from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.invoice_service.app.db import get_session
from services.invoice_service.app.models import Vendor
from services.invoice_service.app.schemas import (
    VendorCreate,
    VendorPage,
    VendorRead,
    VendorReplace,
)

router = APIRouter(prefix="/vendors", tags=["vendors"])
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
async def create_vendor(payload: VendorCreate, session: DbSession) -> Vendor:
    vendor = Vendor(name=payload.name, email=payload.email)
    session.add(vendor)
    await session.commit()
    await session.refresh(vendor)
    return vendor


@router.get("", response_model=VendorPage)
async def list_vendors(
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VendorPage:
    total = await session.scalar(select(func.count()).select_from(Vendor))
    rows = await session.scalars(
        select(Vendor)
        .order_by(Vendor.name, Vendor.id)
        .limit(limit)
        .offset(offset)
    )
    return VendorPage(
        items=list(rows),
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{vendor_id}", response_model=VendorRead)
async def get_vendor(vendor_id: UUID, session: DbSession) -> Vendor:
    vendor = await session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.put("/{vendor_id}", response_model=VendorRead)
async def replace_vendor(
    vendor_id: UUID,
    payload: VendorReplace,
    session: DbSession,
) -> Vendor:
    vendor = await session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    vendor.name = payload.name
    vendor.email = payload.email
    vendor.is_active = payload.is_active
    await session.commit()
    await session.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(vendor_id: UUID, session: DbSession) -> Response:
    vendor = await session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    await session.delete(vendor)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a vendor that has invoices",
        ) from None

    return Response(status_code=status.HTTP_204_NO_CONTENT)