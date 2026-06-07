from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.employee import employee_locations

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.company import Company
    from app.models.employee import Employee


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

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

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str | None] = mapped_column(String(80))

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="locations",
    )

    employees: Mapped[list["Employee"]] = relationship(
        "Employee",
        secondary=employee_locations,
        back_populates="locations",
    )

    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="location",
    )