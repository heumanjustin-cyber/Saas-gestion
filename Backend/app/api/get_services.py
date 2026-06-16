from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.service import Service

router = APIRouter()


@router.get("/services")
def get_services(
    db: Session = Depends(get_db)
):
    services = db.query(Service).all()

    return services