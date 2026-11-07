from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import require_my_company
from app.db.dependencies import get_db
from app.models.location import Location
from app.schemas.location import LocationCreate

router = APIRouter()


@router.post("/locations")
def create_location(
    location: LocationCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company = require_my_company(db, current_user, location.company_id)
    new_location = Location(
        company_id=company.id,
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
