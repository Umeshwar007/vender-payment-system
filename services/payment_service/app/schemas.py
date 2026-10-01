from datetime import datetime
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