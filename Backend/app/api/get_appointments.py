from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.appointment import Appointment

router = APIRouter()

def _row(appointment, with_id=True, with_end=True):
    row = {
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
        "estado": appointment.status,
    }
    if with_end:
        row["fin"] = appointment.ends_at
    if with_id:
        row = {"id": str(appointment.id), **row}
    return row


@router.get("/appointments")
def get_appointments(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    appointments = db.query(Appointment).filter(
        Appointment.company_id.in_(my_company_ids(db, current_user))
    ).order_by(Appointment.starts_at).all()
    return [_row(a) for a in appointments]
