from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.appointment import Appointment

router = APIRouter()


@router.get("/appointments/today")
def appointments_today(
    db: Session = Depends(get_db)
):
    appointments = db.query(Appointment).all()

    result = []

    for appointment in appointments:
        if appointment.starts_at.date() == date.today():
            result.append(appointment)

    return result