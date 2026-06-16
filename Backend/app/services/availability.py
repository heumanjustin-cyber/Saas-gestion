from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.blocked_time import BlockedTime
from app.models.employee_schedule import EmployeeSchedule


def get_employee_slots(
    db: Session,
    employee_id: UUID,
    target_date: date,
    duration_minutes: int,
    slot_interval_minutes: int = 15,
) -> list[dict]:
    """
    Devuelve slots disponibles para un empleado en una fecha dada.
    Tiene en cuenta: horario laboral, citas existentes, bloqueos.
    """
    weekday = target_date.weekday()  # 0=lunes

    schedules = db.query(EmployeeSchedule).filter(
        EmployeeSchedule.employee_id == employee_id,
        EmployeeSchedule.weekday == weekday,
    ).all()

    if not schedules:
        return []

    existing_appointments = db.query(Appointment).filter(
        Appointment.employee_id == employee_id,
        Appointment.status.notin_(["cancelled", "no_show"]),
        Appointment.starts_at >= datetime.combine(target_date, time.min),
        Appointment.starts_at < datetime.combine(target_date, time.max),
    ).all()

    blocked_times = db.query(BlockedTime).filter(
        BlockedTime.employee_id == employee_id,
        BlockedTime.starts_at >= datetime.combine(target_date, time.min),
        BlockedTime.starts_at < datetime.combine(target_date, time.max),
    ).all()

    busy_intervals: list[tuple[datetime, datetime]] = []

    for appt in existing_appointments:
        busy_intervals.append((appt.starts_at, appt.ends_at))

    for block in blocked_times:
        busy_intervals.append((block.starts_at, block.ends_at))

    available_slots = []

    for schedule in schedules:
        slot_start = datetime.combine(target_date, schedule.start_time)
        work_end = datetime.combine(target_date, schedule.end_time)
        duration = timedelta(minutes=duration_minutes)
        interval = timedelta(minutes=slot_interval_minutes)

        while slot_start + duration <= work_end:
            slot_end = slot_start + duration

            overlaps = any(
                slot_start < busy_end and slot_end > busy_start
                for busy_start, busy_end in busy_intervals
            )

            if not overlaps:
                available_slots.append({
                    "starts_at": slot_start.isoformat(),
                    "ends_at": slot_end.isoformat(),
                    "available": True,
                })

            slot_start += interval

    return available_slots
