from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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