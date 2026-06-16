from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.employee import Employee

router = APIRouter()


@router.delete("/employees/{employee_id}")
def delete_employee(
    employee_id: UUID,
    db: Session = Depends(get_db)
):
    employee = db.query(Employee).filter(
        Employee.id == employee_id
    ).first()

    if not employee:
        return {
            "error": "Empleado no encontrado"
        }

    db.delete(employee)
    db.commit()

    return {
        "message": "Empleado eliminado"
    }