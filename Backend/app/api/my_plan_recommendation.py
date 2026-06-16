from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.appointment import Appointment

router = APIRouter()


@router.get("/my-plan-recommendation")
def get_plan_recommendation(
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
    ).count()

    if appointments < 20:
        plan = "basic"
    elif appointments < 100:
        plan = "pro"
    else:
        plan = "ia"

    return {
        "recommended_plan": plan
    }