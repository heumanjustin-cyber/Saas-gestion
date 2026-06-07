from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.employee import employee_services

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.company import Company
    from app.models.employee import Employee


class Service(Base, TimestampMixin):
    __tablename__ = "services"

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

    description: Mapped[str | None] = mapped_column(Text)

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="EUR",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    visible_online: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="services",
    )

    employees: Mapped[list["Employee"]] = relationship(
        "Employee",
        secondary=employee_services,
        back_populates="services",
    )

    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="service",
    )