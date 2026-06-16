from datetime import time
from uuid import UUID

from pydantic import BaseModel, field_validator


class EmployeeScheduleCreate(BaseModel):
    employee_id: UUID
    weekday: int
    start_time: time
    end_time: time

    @field_validator("weekday")
    @classmethod
    def valid_weekday(cls, v):
        if v < 0 or v > 6:
            raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday)")
        return v

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v


class EmployeeScheduleResponse(BaseModel):
    id: UUID
    employee_id: UUID
    weekday: int
    start_time: time
    end_time: time

    model_config = {"from_attributes": True}
