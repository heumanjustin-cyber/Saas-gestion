from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.employee import Employee
from app.models.location import Location
from app.models.service import Service

router = APIRouter()


@router.get("/dashboard")
def dashboard(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ids = my_company_ids(db, current_user)
    return {
        "companies": len(ids),
        "locations": db.query(Location).filter(Location.company_id.in_(ids)).count(),
        "employees": db.query(Employee).filter(Employee.company_id.in_(ids)).count(),
        "clients": db.query(Client).filter(Client.company_id.in_(ids)).count(),
        "services": db.query(Service).filter(Service.company_id.in_(ids)).count(),
        "appointments": db.query(Appointment).filter(Appointment.company_id.in_(ids)).count(),
    }
