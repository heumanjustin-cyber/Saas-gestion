from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.company import Company
from app.models.location import Location
from app.models.employee import Employee
from app.models.client import Client
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.user import User
from app.schemas.company import CompanyCreate

from fastapi import APIRouter, Depends

router = APIRouter()


@router.post("/companies")
def create_company(
    company: CompanyCreate,
    db: Session = Depends(get_db)
):
    new_company = Company(
        name=company.name,
        slug=company.slug
    )

    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    return {
        "id": str(new_company.id),
        "name": new_company.name,
        "slug": new_company.slug
    }