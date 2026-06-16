from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.service import Service
from app.models.appointment import Appointment

router = APIRouter()


@router.get("/my-service-revenue")
def get_service_revenue(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company_ids = [
        company.id
        for company in db.query(Company).filter(
            Company.owner_user_id == current_user.id
        ).all()
    ]

    services = db.query(Service).filter(
        Service.company_id.in_(company_ids)
    ).all()

    result = []

    for service in services:

        appointments = db.query(Appointment).filter(
            Appointment.service_id == service.id
        ).count()

        revenue = appointments * float(service.price)

        result.append({
            "service": service.name,
            "appointments": appointments,
            "revenue": revenue
        })

    return result