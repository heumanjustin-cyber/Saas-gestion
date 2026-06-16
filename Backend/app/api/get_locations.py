from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.location import Location

router = APIRouter()


@router.get("/locations")
def get_locations(
    db: Session = Depends(get_db)
):
    locations = db.query(Location).all()

    return locations