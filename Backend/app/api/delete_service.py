from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.service import Service

router = APIRouter()


@router.delete("/services/{service_id}")
def delete_service(
    service_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    obj = db.query(Service).filter(
        Service.id == service_id,
        Service.company_id.in_(my_company_ids(db, current_user)),
    ).first()

    if not obj:
        # 404 también si es de otra empresa: no se revela que existe
        return JSONResponse(status_code=404, content={"error": "Servicio no encontrado", "detail": "Servicio no encontrado"})

    db.delete(obj)
    db.commit()

    return {
        "message": "Servicio eliminado"
    }
