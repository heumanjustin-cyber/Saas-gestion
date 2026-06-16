from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.appointment import Appointment

router = APIRouter()


@router.delete("/appointments/{appointment_id}")
def delete_appointment(
    appointment_id: UUID,
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()

    if not appointment:
        return {
            "error": "Cita no encontrada"
        }

    db.delete(appointment)
    db.commit()

    return {
        "message": "Cita eliminada"
    }