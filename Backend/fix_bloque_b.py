# Fix resource_booking.py
content = """from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.dependencies import get_db
from app.models.resource_booking import ResourceBooking
from app.schemas.resource_booking import ResourceBookingCreate
from app.services.appointment_service import check_resource_available

router = APIRouter()

@router.post("/resource-bookings")
def create_resource_booking(
    booking: ResourceBookingCreate,
    db: Session = Depends(get_db)
):
    if not check_resource_available(db, booking.resource_id, booking.starts_at, booking.ends_at):
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Resource already booked at this time")

    new_booking = ResourceBooking(
        resource_id=booking.resource_id,
        appointment_id=booking.appointment_id,
        starts_at=booking.starts_at,
        ends_at=booking.ends_at,
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return {"id": str(new_booking.id)}

@router.get("/resource-bookings")
def get_resource_bookings(db: Session = Depends(get_db)):
    return db.query(ResourceBooking).all()
"""
open("app/api/resource_booking.py", "w").write(content)
print("resource_booking.py OK")

# Fix resource.py - quitar UUID() cast + usar UUID en schema
content = """from uuid import UUID
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
    company = db.query(Company).filter(Company.id == resource.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    new_resource = Resource(
        company_id=resource.company_id,
        location_id=resource.location_id,
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
        "company_id": str(new_resource.company_id),
    }

@router.get("/resources")
def get_resources(db: Session = Depends(get_db)):
    return db.query(Resource).all()
"""
open("app/api/resource.py", "w").write(content)
print("resource.py OK")

# Fix schemas/resource.py - usar UUID
content = """from uuid import UUID
from pydantic import BaseModel

class ResourceCreate(BaseModel):
    company_id: UUID
    location_id: UUID | None = None
    name: str
    resource_type: str
    description: str | None = None
"""
open("app/schemas/resource.py", "w").write(content)
print("schemas/resource.py OK")
