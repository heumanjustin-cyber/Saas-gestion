from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models.company import Company
from app.models.service import Service
from app.schemas.service import ServiceCreate

router = APIRouter()


@router.post("/services")
def create_service(
    service: ServiceCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.id == UUID(service.company_id)
    ).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    if company.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not own this company"
        )

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