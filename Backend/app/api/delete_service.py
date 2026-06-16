from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.service import Service

router = APIRouter()


@router.delete("/services/{service_id}")
def delete_service(
    service_id: UUID,
    db: Session = Depends(get_db)
):
    service = db.query(Service).filter(
        Service.id == service_id
    ).first()

    if not service:
        return {
            "error": "Servicio no encontrado"
        }

    db.delete(service)
    db.commit()

    return {
        "message": "Servicio eliminado"
    }