from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.appointment import Appointment

router = APIRouter()


@router.get("/appointments")
def get_appointments(
    db: Session = Depends(get_db)
):
    appointments = db.query(Appointment).all()

    result = []

    for appointment in appointments:
        result.append(
            {
                "id": str(appointment.id),
                "cliente": (
                    f"{appointment.client.first_name} {appointment.client.last_name}"
                    if appointment.client
                    else None
                ),
                "empleado": (
                    f"{appointment.employee.first_name} {appointment.employee.last_name}"
                    if appointment.employee
                    else None
                ),
                "servicio": (
                    appointment.service.name
                    if appointment.service
                    else None
                ),
                "inicio": appointment.starts_at,
                "fin": appointment.ends_at,
                "estado": appointment.status,
            }
        )

    return result