from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.employee import Employee
from app.models.appointment import Appointment
from app.models.service import Service

router = APIRouter()


@router.get("/my-employee-performance")
def get_employee_performance(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company_ids = [
        company.id
        for company in db.query(Company).filter(
            Company.owner_user_id == current_user.id
        ).all()
    ]

    employees = db.query(Employee).filter(
        Employee.company_id.in_(company_ids)
    ).all()

    result = []

    for employee in employees:

        appointments = db.query(Appointment).filter(
            Appointment.employee_id == employee.id
        ).all()

        revenue = 0

        for appointment in appointments:

            if appointment.service_id:

                service = db.query(Service).filter(
                    Service.id == appointment.service_id
                ).first()

                if service:
                    revenue += float(service.price)

        result.append({
            "employee": f"{employee.first_name} {employee.last_name}",
            "appointments": len(appointments),
            "revenue": revenue
        })

    return result