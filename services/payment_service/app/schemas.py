from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentRunCreate(BaseModel):
    invoice_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("invoice_ids")
    @classmethod
    def invoice_ids_must_be_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("invoice_ids must not contain duplicates")
        return value


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    amount_cents: int
    status: str
    bank_reference: UUID | None


class PaymentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    total_cents: int
    created_at: datetime
    completed_at: datetime | None
    payments: list[PaymentRead] = Field(default_factory=list)


class VendorAgingRead(BaseModel):
    vendor_id: UUID
    current_cents: int
    days_1_30_cents: int
    days_31_60_cents: int
    days_61_90_cents: int
    days_90_plus_cents: int
    total_outstanding_cents: int
    vendor_rank: int
    share_pct: float


class AgingReportRead(BaseModel):
    as_of: date
    page: int
    page_size: int
    total_count: int
    total_pages: int
    vendors: list[VendorAgingRead]