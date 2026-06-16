from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class BlockedTimeCreate(BaseModel):
    employee_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: str | None = None

    @field_validator("ends_at")
    @classmethod
    def ends_after_starts(cls, v, info):
        if "starts_at" in info.data and v <= info.data["starts_at"]:
            raise ValueError("ends_at must be after starts_at")
        return v


class BlockedTimeResponse(BaseModel):
    id: UUID
    employee_id: UUID | None
    starts_at: datetime
    ends_at: datetime
    reason: str | None

    model_config = {"from_attributes": True}
