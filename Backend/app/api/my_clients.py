from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models.client import Client
from app.models.company import Company

router = APIRouter()


@router.get("/my-clients")
def get_my_clients(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company_ids = [
        company.id
        for company in db.query(Company).filter(
            Company.owner_user_id == current_user.id
        ).all()
    ]

    clients = db.query(Client).filter(
        Client.company_id.in_(company_ids)
    ).all()

    return clients