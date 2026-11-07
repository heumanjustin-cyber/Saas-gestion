from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.service import Service

router = APIRouter()


@router.get("/services")
def get_services(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Service).filter(
        Service.company_id.in_(my_company_ids(db, current_user))
    ).all()
