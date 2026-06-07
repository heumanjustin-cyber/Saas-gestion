from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.company import Company
    from app.models.location import Location
    from app.models.service import Service
    from app.models.user import User


employee_locations = Table(
    "employee_locations",
    Base.metadata,
    Column(
        "employee_id",
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "location_id",
        PG_UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

employee_services = Table(
    "employee_services",
    Base.metadata,
    Column(
        "employee_id",
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "service_id",
        PG_UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str | None] = mapped_column(String(100))
    public_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    accepts_online_bookings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="employees",
    )

    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="employee_profile",
    )

    locations: Mapped[list["Location"]] = relationship(
        "Location",
        secondary=employee_locations,
        back_populates="employees",
    )

    services: Mapped[list["Service"]] = relationship(
        "Service",
        secondary=employee_services,
        back_populates="employees",
    )

    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="employee",
    )