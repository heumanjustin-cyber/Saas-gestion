from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.client import Client

router = APIRouter()


@router.delete("/clients/{client_id}")
def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db)
):
    client = db.query(Client).filter(
        Client.id == client_id
    ).first()

    if not client:
        return {
            "error": "Cliente no encontrado"
        }

    db.delete(client)
    db.commit()

    return {
        "message": "Cliente eliminado"
    }