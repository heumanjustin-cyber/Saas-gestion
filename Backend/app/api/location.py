from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.location import Location
from app.schemas.location import LocationCreate

router = APIRouter()


@router.post("/locations")
def create_location(
    location: LocationCreate,
    db: Session = Depends(get_db)
):
    new_location = Location(
        company_id=UUID(location.company_id),
        name=location.name
    )

    db.add(new_location)
    db.commit()
    db.refresh(new_location)

    return {
        "id": str(new_location.id),
        "name": new_location.name,
        "company_id": str(new_location.company_id)
    }