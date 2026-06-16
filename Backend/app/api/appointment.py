from datetime import date, datetime, time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models.appointment import Appointment
from app.models.company import Company
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.services.appointment_service import (
    check_blocked_time,
    check_double_booking,
    check_schedule,
    register_history,
)

router = APIRouter()


def get_company_or_403(db, company_id, user_id):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return company


@router.post("/appointments", response_model=AppointmentResponse)
def create_appointment(
    data: AppointmentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_company_or_403(db, data.company_id, current_user.id)

    if data.employee_id:
        if not check_schedule(db, data.employee_id, data.starts_at, data.ends_at):
            raise HTTPException(status_code=409, detail="Employee is not working at this time")
        if check_double_booking(db, data.employee_id, data.starts_at, data.ends_at):
            raise HTTPException(status_code=409, detail="Employee already booked at this time")
        if check_blocked_time(db, data.employee_id, data.starts_at, data.ends_at):
            raise HTTPException(status_code=409, detail="Employee is blocked at this time")

    appt = Appointment(**data.model_dump())
    db.add(appt)
    db.flush()
    register_history(db, appt.id, "created", None, str(data.starts_at), str(current_user.id))
    db.commit()
    db.refresh(appt)
    return appt


@router.get("/my/appointments", response_model=list[AppointmentResponse])
def list_appointments(
    company_id: UUID = Query(...),
    target_date: date | None = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_company_or_403(db, company_id, current_user.id)
    q = db.query(Appointment).filter(Appointment.company_id == company_id)
    if target_date:
        q = q.filter(
            Appointment.starts_at >= datetime.combine(target_date, time.min),
            Appointment.starts_at < datetime.combine(target_date, time.max),
        )
    return q.order_by(Appointment.starts_at).all()


@router.get("/my/appointments/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    get_company_or_403(db, appt.company_id, current_user.id)
    return appt


@router.patch("/my/appointments/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: UUID,
    data: AppointmentUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    get_company_or_403(db, appt.company_id, current_user.id)

    employee_id = data.employee_id or appt.employee_id
    starts = data.starts_at or appt.starts_at
    ends = data.ends_at or appt.ends_at

    if employee_id:
        if not check_schedule(db, employee_id, starts, ends):
            raise HTTPException(status_code=409, detail="Employee is not working at this time")
        if check_double_booking(db, employee_id, starts, ends, exclude_id=appointment_id):
            raise HTTPException(status_code=409, detail="Employee already booked at this time")

    old = str(appt.starts_at)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(appt, field, value)

    register_history(db, appt.id, "updated", old, str(starts), str(current_user.id))
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/my/appointments/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: UUID,
    data: AppointmentCancel,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    get_company_or_403(db, appt.company_id, current_user.id)

    if appt.status == "cancelled":
        raise HTTPException(status_code=400, detail="Already cancelled")

    old = appt.status
    appt.status = "cancelled"
    appt.cancelled_reason = data.reason
    register_history(db, appt.id, "cancelled", old, "cancelled", str(current_user.id))
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/my/appointments/{appointment_id}/reschedule", response_model=AppointmentResponse)
def reschedule_appointment(
    appointment_id: UUID,
    data: AppointmentReschedule,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    get_company_or_403(db, appt.company_id, current_user.id)

    if appt.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot reschedule cancelled appointment")

    if appt.employee_id:
        if not check_schedule(db, appt.employee_id, data.starts_at, data.ends_at):
            raise HTTPException(status_code=409, detail="Employee is not working at this time")
        if check_double_booking(db, appt.employee_id, data.starts_at, data.ends_at, exclude_id=appointment_id):
            raise HTTPException(status_code=409, detail="Employee already booked at this time")
        if check_blocked_time(db, appt.employee_id, data.starts_at, data.ends_at):
            raise HTTPException(status_code=409, detail="Employee is blocked at this time")

    old = str(appt.starts_at)
    appt.starts_at = data.starts_at
    appt.ends_at = data.ends_at
    appt.status = "rescheduled"
    register_history(db, appt.id, "rescheduled", old, str(data.starts_at), str(current_user.id))
    db.commit()
    db.refresh(appt)
    return appt


@router.get("/my/appointments/{appointment_id}/history")
def get_appointment_history(
    appointment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    get_company_or_403(db, appt.company_id, current_user.id)
    return appt.history


@router.get("/my/agenda")
def get_agenda(
    company_id: UUID = Query(...),
    target_date: date = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_company_or_403(db, company_id, current_user.id)
    appointments = db.query(Appointment).filter(
        Appointment.company_id == company_id,
        Appointment.status.notin_(["cancelled"]),
        Appointment.starts_at >= datetime.combine(target_date, time.min),
        Appointment.starts_at < datetime.combine(target_date, time.max),
    ).order_by(Appointment.starts_at).all()

    return {
        "date": str(target_date),
        "total": len(appointments),
        "appointments": [
            {
                "id": str(a.id),
                "employee_id": str(a.employee_id),
                "client_id": str(a.client_id) if a.client_id else None,
                "service_id": str(a.service_id) if a.service_id else None,
                "starts_at": a.starts_at.isoformat(),
                "ends_at": a.ends_at.isoformat(),
                "status": a.status,
            }
            for a in appointments
        ],
    }
