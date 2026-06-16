from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.appointment import Appointment
from app.models.employee import Employee

router = APIRouter()


@router.get("/my-top-employees")
def get_my_top_employees(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company_ids = [
        company.id
        for company in db.query(Company).filter(
            Company.owner_user_id == current_user.id
        ).all()
    ]

    appointments = db.query(Appointment).filter(
        Appointment.company_id.in_(company_ids)
    ).all()

    counter = Counter()

    for appointment in appointments:
        if appointment.employee_id:
            counter[str(appointment.employee_id)] += 1

    result = []

    for employee_id, count in counter.most_common():
        employee = db.query(Employee).filter(
            Employee.id == employee_id
        ).first()

        if employee:
            result.append({
                "employee": f"{employee.first_name} {employee.last_name}",
                "appointments": count
            })

    return result