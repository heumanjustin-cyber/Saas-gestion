from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db

from app.models.company import Company
from app.models.location import Location
from app.models.employee import Employee
from app.models.client import Client
from app.models.service import Service
from app.models.appointment import Appointment

router = APIRouter()


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db)
):
    return {
        "companies": db.query(Company).count(),
        "locations": db.query(Location).count(),
        "employees": db.query(Employee).count(),
        "clients": db.query(Client).count(),
        "services": db.query(Service).count(),
        "appointments": db.query(Appointment).count(),
    }