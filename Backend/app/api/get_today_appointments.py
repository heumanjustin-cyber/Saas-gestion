from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.tenancy import my_company_ids
from app.db.dependencies import get_db
from app.models.appointment import Appointment

router = APIRouter()
TZ = ZoneInfo("Europe/Madrid")


@router.get("/appointments/today")
def appointments_today(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # «Hoy» en hora de Madrid (antes comparaba fechas UTC y fallaba cerca de medianoche)
    today = datetime.now(timezone.utc).astimezone(TZ).date()
    start = datetime.combine(today, time.min, tzinfo=TZ)
    return db.query(Appointment).filter(
        Appointment.company_id.in_(my_company_ids(db, current_user)),
        Appointment.starts_at >= start,
        Appointment.starts_at < start + timedelta(days=1),
    ).order_by(Appointment.starts_at).all()
