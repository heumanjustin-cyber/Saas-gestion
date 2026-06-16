from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.appointment import Appointment
from app.models.service import Service

router = APIRouter()


@router.get("/my-top-services")
def get_my_top_services(
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
        if appointment.service_id:
            counter[str(appointment.service_id)] += 1

    result = []

    for service_id, count in counter.most_common():
        service = db.query(Service).filter(
            Service.id == service_id
        ).first()

        if service:
            result.append({
                "service": service.name,
                "appointments": count
            })

    return result