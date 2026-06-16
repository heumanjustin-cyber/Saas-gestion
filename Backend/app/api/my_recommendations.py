from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.client import Client
from app.models.employee import Employee
from app.models.appointment import Appointment

router = APIRouter()


@router.get("/my-recommendations")
def get_my_recommendations(
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

    employees = db.query(Employee).filter(
        Employee.company_id.in_(company_ids)
    ).count()

    appointments = db.query(Appointment).filter(
        Appointment.company_id.in_(company_ids)
    ).count()

    recommendations = []

    if employees <= 1:
        recommendations.append(
            "Considera añadir un segundo empleado"
        )

    if clients < 10:
        recommendations.append(
            "Necesitas captar más clientes"
        )

    if appointments < 20:
        recommendations.append(
            "Activa campañas para aumentar reservas"
        )

    return recommendations