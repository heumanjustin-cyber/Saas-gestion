from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.client import Client
from app.models.appointment import Appointment

router = APIRouter()


@router.get("/my-growth-opportunities")
def get_growth_opportunities(
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
    ).count()

    appointments = db.query(Appointment).filter(
        Appointment.company_id.in_(company_ids)
    ).count()

    opportunities = []

    if clients > 0:
        opportunities.append(
            f"Tienes {clients} clientes que podrían volver"
        )

    if appointments > 0:
        opportunities.append(
            "Puedes enviar recordatorios automáticos"
        )

    opportunities.append(
        "Puedes activar reservas online"
    )

    return opportunities