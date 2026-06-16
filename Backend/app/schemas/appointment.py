from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class AppointmentCreate(BaseModel):
    company_id: UUID
    location_id: UUID | None = None
    client_id: UUID | None = None
    employee_id: UUID | None = None
    service_id: UUID | None = None
    starts_at: datetime
    ends_at: datetime
    status: str = "scheduled"
    source: str = "internal"
    booking_channel: str = "web"
    final_price: Decimal | None = None
    notes: str | None = None

    @field_validator("ends_at")
    @classmethod
    def ends_after_starts(cls, v, info):
        if "starts_at" in info.data and v <= info.data["starts_at"]:
            raise ValueError("ends_at must be after starts_at")
        return v


class AppointmentResponse(BaseModel):
    id: UUID
    company_id: UUID
    location_id: UUID | None
    client_id: UUID | None
    employee_id: UUID | None
    service_id: UUID | None
    starts_at: datetime
    ends_at: datetime
    status: str
    source: str
    booking_channel: str
    final_price: Decimal | None
    notes: str | None

    model_config = {"from_attributes": True}
