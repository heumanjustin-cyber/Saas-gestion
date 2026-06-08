print("APPOINTMENT ROUTER CARGADO")

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.appointment import Appointment
from app.schemas.appointment import AppointmentCreate

router = APIRouter()


@router.post("/appointments")
def create_appointment(
    appointment: AppointmentCreate,
    db: Session = Depends(get_db)
):
    new_appointment = Appointment(
        company_id=UUID(appointment.company_id),
        client_id=UUID(appointment.client_id),
        employee_id=UUID(appointment.employee_id),
        service_id=UUID(appointment.service_id),
        starts_at=datetime.fromisoformat(appointment.starts_at),
        ends_at=datetime.fromisoformat(appointment.ends_at),
    )

    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)

    return {
        "id": str(new_appointment.id),
        "client_id": str(new_appointment.client_id),
        "employee_id": str(new_appointment.employee_id),
        "service_id": str(new_appointment.service_id)
    }