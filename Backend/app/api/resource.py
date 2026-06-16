from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

from app.models.company import Company
from app.models.resource import Resource

from app.schemas.resource import ResourceCreate

router = APIRouter()


@router.post("/resources")
def create_resource(
    resource: ResourceCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.id == UUID(resource.company_id)
    ).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    if company.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not own this company"
        )

    new_resource = Resource(
        company_id=UUID(resource.company_id),
        location_id=UUID(resource.location_id)
        if resource.location_id
        else None,
        name=resource.name,
        resource_type=resource.resource_type,
        description=resource.description,
    )

    db.add(new_resource)
    db.commit()
    db.refresh(new_resource)

    return {
        "id": str(new_resource.id),
        "name": new_resource.name,
        "resource_type": new_resource.resource_type,
        "company_id": str(new_resource.company_id)
    }


@router.get("/resources")
def get_resources(
    db: Session = Depends(get_db)
):
    resources = db.query(Resource).all()

    return resources