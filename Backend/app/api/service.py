from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.service import Service
from app.schemas.service import ServiceCreate

router = APIRouter()


@router.post("/services")
def create_service(
    service: ServiceCreate,
    db: Session = Depends(get_db)
):
    new_service = Service(
        company_id=UUID(service.company_id),
        name=service.name,
        duration_minutes=service.duration_minutes,
        price=service.price
    )

    db.add(new_service)
    db.commit()
    db.refresh(new_service)

    return {
        "id": str(new_service.id),
        "name": new_service.name,
        "duration_minutes": new_service.duration_minutes,
        "price": float(new_service.price),
        "company_id": str(new_service.company_id)
    }