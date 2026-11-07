from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.client import Client

router = APIRouter()


@router.delete("/clients/{client_id}")
def delete_client(
    client_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    obj = db.query(Client).filter(
        Client.id == client_id,
        Client.company_id.in_(my_company_ids(db, current_user)),
    ).first()

    if not obj:
        # 404 también si es de otra empresa: no se revela que existe
        return JSONResponse(status_code=404, content={"error": "Cliente no encontrado", "detail": "Cliente no encontrado"})

    db.delete(obj)
    db.commit()

    return {
        "message": "Cliente eliminado"
    }
