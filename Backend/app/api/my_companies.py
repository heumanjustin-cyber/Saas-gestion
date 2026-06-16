from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models.company import Company

router = APIRouter()


@router.get("/my-companies")
def get_my_companies(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    companies = db.query(
        Company
    ).filter(
        Company.owner_user_id == current_user.id
    ).all()

    return companies