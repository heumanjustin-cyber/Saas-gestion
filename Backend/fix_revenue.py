revenue_code = """from fastapi import APIRouter, Depends
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
"""
open("app/api/my_revenue.py", "w").write(revenue_code)
print("my_revenue.py OK")

kpis_code = """from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models.company import Company
from app.models.client import Client
from app.models.employee import Employee
from app.models.appointment import Appointment
from app.models.service import Service

router = APIRouter()

@router.get("/my-kpis")
def get_my_kpis(
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
    total = len(appointments)
    average_ticket = round(revenue / total, 2) if total > 0 else 0.0
    return {
        "revenue": round(revenue, 2),
        "appointments": total,
        "clients": db.query(Client).filter(Client.company_id.in_(company_ids)).count(),
        "employees": db.query(Employee).filter(Employee.company_id.in_(company_ids)).count(),
        "average_ticket": average_ticket,
    }
"""
open("app/api/my_kpis.py", "w").write(kpis_code)
print("my_kpis.py OK")
