from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.services.availability import get_employee_slots

router = APIRouter()


@router.get("/my/availability")
def get_availability(
    employee_id: UUID = Query(...),
    target_date: date = Query(...),
    duration_minutes: int = Query(..., ge=5, le=480),
    slot_interval_minutes: int = Query(15, ge=5, le=60),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    slots = get_employee_slots(
        db=db,
        employee_id=employee_id,
        target_date=target_date,
        duration_minutes=duration_minutes,
        slot_interval_minutes=slot_interval_minutes,
    )

    return {
        "employee_id": str(employee_id),
        "date": str(target_date),
        "duration_minutes": duration_minutes,
        "slots": slots,
    }
