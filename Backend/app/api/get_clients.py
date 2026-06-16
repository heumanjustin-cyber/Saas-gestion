from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.client import Client

router = APIRouter()


@router.get("/clients")
def get_clients(
    db: Session = Depends(get_db)
):
    clients = db.query(Client).all()

    return clients