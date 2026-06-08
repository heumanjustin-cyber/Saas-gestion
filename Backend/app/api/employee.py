from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate

router = APIRouter()


@router.post("/employees")
def create_employee(
    employee: EmployeeCreate,
    db: Session = Depends(get_db)
):
    new_employee = Employee(
        company_id=UUID(employee.company_id),
        first_name=employee.first_name,
        last_name=employee.last_name
    )

    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)

    return {
        "id": str(new_employee.id),
        "first_name": new_employee.first_name,
        "last_name": new_employee.last_name,
        "company_id": str(new_employee.company_id)
    }