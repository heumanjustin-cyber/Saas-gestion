from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models.service import Service
from app.models.company import Company

router = APIRouter()


@router.get("/my-services")
def get_my_services(
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

    return services