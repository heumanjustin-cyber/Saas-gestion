from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db

from app.models.resource_booking import (
    ResourceBooking
)

from app.schemas.resource_booking import (
    ResourceBookingCreate,
)

router = APIRouter()


@router.post("/resource-bookings")
def create_resource_booking(
    booking: ResourceBookingCreate,
    db: Session = Depends(get_db)
):
    new_booking = ResourceBooking(
        resource_id=UUID(
            booking.resource_id
        ),
        appointment_id=UUID(
            booking.appointment_id
        ),
        starts_at=datetime.fromisoformat(
            booking.starts_at
        ),
        ends_at=datetime.fromisoformat(
            booking.ends_at
        ),
    )

    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return {
        "id": str(new_booking.id)
    }


@router.get("/resource-bookings")
def get_resource_bookings(
    db: Session = Depends(get_db)
):
    return db.query(
        ResourceBooking
    ).all()