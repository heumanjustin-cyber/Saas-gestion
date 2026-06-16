from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.appointment import Appointment
from app.models.service import Service

router = APIRouter()


@router.get("/my-revenue")
def get_my_revenue(
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

    revenue = 0

    for appointment in appointments:
        if appointment.service_id:
            service = db.query(Service).filter(
                Service.id == appointment.service_id
            ).first()

            if service:
                revenue += float(service.price)

    return {
        "revenue": revenue
    }