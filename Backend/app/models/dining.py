"""Mesas y códigos QR dinámicos.

Cada pieza impresa (pegatina de mesa, display de barra, llavero, vinilo de la
puerta, bolsa de reparto) lleva un QR propio que apunta a /q/<código>. El
destino se cambia desde el sistema sin reimprimir, y cada escaneo cuenta: así
se sabe qué pieza trae pedidos.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

QR_KINDS = ("table", "counter", "display", "keychain", "door", "bag", "flyer", "other")
QR_TARGETS = ("menu", "review", "url")


class DiningTable(Base, TimestampMixin):
    __tablename__ = "dining_tables"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    zone: Mapped[str | None] = mapped_column(String(60))
    seats: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class QrCode(Base, TimestampMixin):
    __tablename__ = "qr_codes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="counter")
    label: Mapped[str | None] = mapped_column(String(120))
    table_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("dining_tables.id", ondelete="SET NULL")
    )
    target: Mapped[str] = mapped_column(String(20), nullable=False, default="menu")
    target_url: Mapped[str | None] = mapped_column(String(500))
    campaign: Mapped[str | None] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    table: Mapped["DiningTable | None"] = relationship("DiningTable")


class QrScan(Base):
    """Un escaneo. Sin IP ni datos personales: solo tipo de dispositivo e idioma."""

    __tablename__ = "qr_scans"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    qr_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("qr_codes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    device: Mapped[str | None] = mapped_column(String(10))
    lang: Mapped[str | None] = mapped_column(String(8))
