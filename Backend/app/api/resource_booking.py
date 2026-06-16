from fastapi import APIRouter, Depends
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
