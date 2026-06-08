from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate

router = APIRouter()


@router.post("/clients")
def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db)
):
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