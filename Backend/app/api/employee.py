from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models.company import Company
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate

router = APIRouter()


@router.post("/employees")
def create_employee(
    employee: EmployeeCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.id == UUID(employee.company_id)
    ).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    if company.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not own this company"
        )

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