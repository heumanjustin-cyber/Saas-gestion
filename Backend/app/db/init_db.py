from __future__ import annotations

from app.db.base import Base
from app.db.database import engine

from app.models.user import User
from app.models.company import Company
from app.models.company_settings import CompanySettings

from app.models.client import Client
from app.models.employee import Employee
from app.models.location import Location
from app.models.service import Service
from app.models.appointment import Appointment

from app.models.permission import Permission
from app.models.role import Role
from app.models.membership import CompanyMembership

from app.models.appointment_history import (
    AppointmentHistory
)

from app.models.resource import Resource

from app.models.employee_schedule import (
    EmployeeSchedule
)

from app.models.blocked_time import (
    BlockedTime
)

from app.models.resource_booking import (
    ResourceBooking
)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()