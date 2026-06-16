from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.appointment_history import AppointmentHistory
from app.models.blocked_time import BlockedTime
from app.models.employee_schedule import EmployeeSchedule
from app.models.resource_booking import ResourceBooking


def check_double_booking(
    db: Session,
    employee_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: UUID | None = None,
) -> bool:
    q = db.query(Appointment).filter(
        Appointment.employee_id == employee_id,
        Appointment.status.notin_(["cancelled", "no_show"]),
        Appointment.starts_at < ends_at,
        Appointment.ends_at > starts_at,
    )
    if exclude_id:
        q = q.filter(Appointment.id != exclude_id)
    return q.first() is not None


def check_blocked_time(
    db: Session,
    employee_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> bool:
    return db.query(BlockedTime).filter(
        BlockedTime.employee_id == employee_id,
        BlockedTime.starts_at < ends_at,
        BlockedTime.ends_at > starts_at,
    ).first() is not None


def check_schedule(
    db: Session,
    employee_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> bool:
    weekday = starts_at.weekday()
    slot_start = starts_at.time()
    slot_end = ends_at.time()
    return db.query(EmployeeSchedule).filter(
        EmployeeSchedule.employee_id == employee_id,
        EmployeeSchedule.weekday == weekday,
        EmployeeSchedule.start_time <= slot_start,
        EmployeeSchedule.end_time >= slot_end,
    ).first() is not None


def check_resource_available(
    db: Session,
    resource_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
) -> bool:
    q = db.query(ResourceBooking).filter(
        ResourceBooking.resource_id == resource_id,
        ResourceBooking.starts_at < ends_at,
        ResourceBooking.ends_at > starts_at,
    )
    if exclude_appointment_id:
        q = q.filter(ResourceBooking.appointment_id != exclude_appointment_id)
    return q.first() is None


def register_history(
    db: Session,
    appointment_id: UUID,
    action: str,
    old_value: str | None,
    new_value: str | None,
    created_by: str | None,
):
    db.add(AppointmentHistory(
        appointment_id=appointment_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        created_by=created_by,
    ))
