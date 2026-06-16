from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class ResourceBookingCreate(BaseModel):
    resource_id: UUID
    appointment_id: UUID
    starts_at: datetime
    ends_at: datetime

    @field_validator("ends_at")
    @classmethod
    def ends_after_starts(cls, v, info):
        if "starts_at" in info.data and v <= info.data["starts_at"]:
            raise ValueError("ends_at must be after starts_at")
        return v


class ResourceBookingResponse(BaseModel):
    id: UUID
    resource_id: UUID
    appointment_id: UUID
    starts_at: datetime
    ends_at: datetime

    model_config = {"from_attributes": True}
