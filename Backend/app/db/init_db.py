from __future__ import annotations

from app.db.base import Base
from app.db.database import engine
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.company import Company
from app.models.employee import Employee
from app.models.location import Location
from app.models.service import Service
from app.models.user import User


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()