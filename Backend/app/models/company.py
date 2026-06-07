from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.client import Client
    from app.models.employee import Employee
    from app.models.location import Location
    from app.models.service import Service


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    slug: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    country: Mapped[str | None] = mapped_column(String(80))

    timezone: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="Europe/Madrid",
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="EUR",
    )

    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="es",
    )

    plan: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="free",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    locations: Mapped[list["Location"]] = relationship(
        "Location",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    employees: Mapped[list["Employee"]] = relationship(
        "Employee",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    clients: Mapped[list["Client"]] = relationship(
        "Client",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    services: Mapped[list["Service"]] = relationship(
        "Service",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="company",
        cascade="all, delete-orphan",
    )