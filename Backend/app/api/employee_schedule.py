from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db

from app.models.employee_schedule import EmployeeSchedule

from app.schemas.employee_schedule import (
    EmployeeScheduleCreate,
)

router = APIRouter()


@router.post("/employee-schedules")
def create_employee_schedule(
    schedule: EmployeeScheduleCreate,
    db: Session = Depends(get_db)
):
    new_schedule = EmployeeSchedule(
        employee_id=UUID(schedule.employee_id),
        weekday=schedule.weekday,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
    )

    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)

    return {
        "id": str(new_schedule.id)
    }


@router.get("/employee-schedules")
def get_employee_schedules(
    db: Session = Depends(get_db)
):
    return db.query(
        EmployeeSchedule
    ).all()