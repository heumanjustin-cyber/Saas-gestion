# Fix availability.py - timezone aware comparisons
content = """from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.models.appointment import Appointment
from app.models.blocked_time import BlockedTime
from app.models.employee_schedule import EmployeeSchedule

TZ = ZoneInfo("Europe/Madrid")

def get_employee_slots(
    db: Session,
    employee_id: UUID,
    target_date: date,
    duration_minutes: int,
    slot_interval_minutes: int = 15,
) -> list[dict]:
    weekday = target_date.weekday()
    schedules = db.query(EmployeeSchedule).filter(
        EmployeeSchedule.employee_id == employee_id,
        EmployeeSchedule.weekday == weekday,
    ).all()
    if not schedules:
        return []

    day_start = datetime.combine(target_date, time.min).replace(tzinfo=TZ)
    day_end = datetime.combine(target_date, time.max).replace(tzinfo=TZ)

    existing_appointments = db.query(Appointment).filter(
        Appointment.employee_id == employee_id,
        Appointment.status.notin_(["cancelled", "no_show"]),
        Appointment.starts_at >= day_start,
        Appointment.starts_at < day_end,
    ).all()

    blocked_times = db.query(BlockedTime).filter(
        BlockedTime.employee_id == employee_id,
        BlockedTime.starts_at >= day_start,
        BlockedTime.starts_at < day_end,
    ).all()

    busy_intervals: list[tuple[datetime, datetime]] = []
    for appt in existing_appointments:
        busy_intervals.append((appt.starts_at.astimezone(TZ), appt.ends_at.astimezone(TZ)))
    for block in blocked_times:
        busy_intervals.append((block.starts_at.astimezone(TZ), block.ends_at.astimezone(TZ)))

    available_slots = []
    for schedule in schedules:
        slot_start = datetime.combine(target_date, schedule.start_time, tzinfo=TZ)
        work_end = datetime.combine(target_date, schedule.end_time, tzinfo=TZ)
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
"""
open("app/services/availability.py", "w").write(content)
print("availability.py OK")

# Fix register.py - proper HTTP codes + return token
content = """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt
from datetime import datetime, timedelta
from app.db.dependencies import get_db
from app.models.user import User
from app.schemas.register import RegisterRequest
from app.core.security import hash_password
from app.core.config import SECRET_KEY, ALGORITHM

router = APIRouter()

@router.post("/register")
def register(
    user: RegisterRequest,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email ya registrado")

    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password),
        full_name=user.full_name,
        is_active=True,
        is_verified=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    expire = datetime.utcnow() + timedelta(hours=24)
    token = jwt.encode({"sub": str(new_user.id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "full_name": new_user.full_name,
        "access_token": token,
        "token_type": "bearer",
    }
"""
open("app/api/register.py", "w").write(content)
print("register.py OK")
