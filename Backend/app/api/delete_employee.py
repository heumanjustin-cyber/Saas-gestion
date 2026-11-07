from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.employee import Employee

router = APIRouter()


@router.delete("/employees/{employee_id}")
def delete_employee(
    employee_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    obj = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.company_id.in_(my_company_ids(db, current_user)),
    ).first()

    if not obj:
        # 404 también si es de otra empresa: no se revela que existe
        return JSONResponse(status_code=404, content={"error": "Empleado no encontrado", "detail": "Empleado no encontrado"})

    db.delete(obj)
    db.commit()

    return {
        "message": "Empleado eliminado"
    }
