from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.appointment import Appointment

router = APIRouter()


@router.delete("/appointments/{appointment_id}")
def delete_appointment(
    appointment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    obj = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.company_id.in_(my_company_ids(db, current_user)),
    ).first()

    if not obj:
        # 404 también si es de otra empresa: no se revela que existe
        return JSONResponse(status_code=404, content={"error": "Cita no encontrada", "detail": "Cita no encontrada"})

    db.delete(obj)
    db.commit()

    return {
        "message": "Cita eliminada"
    }
