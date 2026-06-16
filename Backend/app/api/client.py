from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models.client import Client
from app.models.company import Company
from app.schemas.client import ClientCreate

router = APIRouter()


@router.post("/clients")
def create_client(
    client: ClientCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.id == UUID(client.company_id)
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

    new_client = Client(
        company_id=UUID(client.company_id),
        first_name=client.first_name,
        last_name=client.last_name,
        phone=client.phone
    )

    db.add(new_client)
    db.commit()
    db.refresh(new_client)

    return {
        "id": str(new_client.id),
        "first_name": new_client.first_name,
        "last_name": new_client.last_name,
        "phone": new_client.phone
    }