from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from services.invoice_service.app.domain import InvoiceStatus


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)


class VendorReplace(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    is_active: bool = True


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str | None
    is_active: bool
    created_at: datetime


class VendorPage(BaseModel):
    items: list[VendorRead]
    total: int
    limit: int
    offset: int

class InvoiceLineCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Annotated[StrictInt, Field(gt=0)]
    unit_price_cents: Annotated[StrictInt, Field(ge=0)]


class InvoiceCreate(BaseModel):
    vendor_id: UUID
    invoice_number: str = Field(min_length=1, max_length=100)
    issued_date: date
    due_date: date
    lines: list[InvoiceLineCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def due_date_not_before_issue_date(self):
        if self.due_date < self.issued_date:
            raise ValueError("Due date cannot be before issue date")
        return self


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    description: str
    quantity: int
    unit_price_cents: int
    line_total_cents: int


class InvoiceDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vendor_id: UUID
    invoice_number: str
    status: InvoiceStatus
    issued_date: date
    due_date: date
    total_cents: int
    amount_paid_cents: int
    lines: list[InvoiceLineRead]


class InvoiceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vendor_id: UUID
    invoice_number: str
    status: InvoiceStatus
    issued_date: date
    due_date: date
    total_cents: int
    amount_paid_cents: int
    created_at: datetime


class InvoicePage(BaseModel):
    items: list[InvoiceSummary]
    total: int
    limit: int
    offset: int

class InvoiceStatusChange(BaseModel):
    status: InvoiceStatus


class InvoiceUpdate(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=100)
    issued_date: date
    due_date: date
    lines: list[InvoiceLineCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def due_date_not_before_issue_date(self):
        if self.due_date < self.issued_date:
            raise ValueError("Due date cannot be before issue date")
        return self