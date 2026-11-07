from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import get_mine_or_404, my_company_ids
from app.db.dependencies import get_db
from app.models.appointment import Appointment
from app.models.resource import Resource
from app.models.resource_booking import ResourceBooking
from app.schemas.resource_booking import ResourceBookingCreate
from app.services.appointment_service import check_resource_available

router = APIRouter()


@router.post("/resource-bookings")
def create_resource_booking(
    booking: ResourceBookingCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resource = get_mine_or_404(db, Resource, booking.resource_id, current_user, "Recurso")
    appointment = get_mine_or_404(db, Appointment, booking.appointment_id, current_user, "Cita")
    if appointment.company_id != resource.company_id:
        raise HTTPException(status_code=422, detail="El recurso y la cita son de empresas distintas")
    if not check_resource_available(db, booking.resource_id, booking.starts_at, booking.ends_at):
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
def get_resource_bookings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(ResourceBooking).join(Resource, Resource.id == ResourceBooking.resource_id).filter(
        Resource.company_id.in_(my_company_ids(db, current_user))
    ).all()
