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
    company_ids = [c.id for c in db.query(Company).filter(
        Company.owner_user_id == current_user.id).all()]
    appointments = db.query(Appointment).filter(
        Appointment.company_id.in_(company_ids),
        Appointment.status.notin_(["cancelled", "no_show"]),
    ).all()
    service_ids = list({a.service_id for a in appointments if a.service_id})
    services = {s.id: s for s in db.query(Service).filter(Service.id.in_(service_ids)).all()}
    revenue = 0.0
    for a in appointments:
        if a.final_price is not None:
            revenue += float(a.final_price)
        elif a.service_id and a.service_id in services:
            revenue += float(services[a.service_id].price)
    return {"revenue": round(revenue, 2), "appointments_counted": len(appointments)}
