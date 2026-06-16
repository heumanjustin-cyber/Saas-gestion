from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.company import Company
    from app.models.employee import Employee
    from app.models.location import Location
    from app.models.service import Service
    from app.models.appointment_history import AppointmentHistory


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), index=True)
    client_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    employee_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    service_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("services.id", ondelete="SET NULL"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled")
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="internal")
    booking_channel: Mapped[str] = mapped_column(String(50), nullable=False, default="web")
    final_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    cancelled_reason: Mapped[str | None] = mapped_column(String(255))

    company: Mapped["Company"] = relationship("Company", back_populates="appointments")
    location: Mapped["Location | None"] = relationship("Location", back_populates="appointments")
    client: Mapped["Client | None"] = relationship("Client", back_populates="appointments")
    employee: Mapped["Employee | None"] = relationship("Employee", back_populates="appointments")
    service: Mapped["Service | None"] = relationship("Service", back_populates="appointments")
    history: Mapped[list["AppointmentHistory"]] = relationship("AppointmentHistory", back_populates="appointment", cascade="all, delete-orphan")
