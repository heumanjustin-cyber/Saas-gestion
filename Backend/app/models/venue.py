"""Perfil de hostelería de una empresa: lo que ve el cliente al escanear el QR.

Una sola fila por empresa. Sustituye al JSON estático que otros sistemas
publican en GitHub Pages: aquí el dueño cambia horario, oferta del día o
pausa los pedidos y el cambio se ve al instante, sin reimprimir nada.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class VenueProfile(Base, TimestampMixin):
    __tablename__ = "venue_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Identidad
    display_name: Mapped[str | None] = mapped_column(String(150))
    tagline: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    cuisine: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # halal, terraza, vegano...
    logo_url: Mapped[str | None] = mapped_column(String(500))
    cover_url: Mapped[str | None] = mapped_column(String(500))
    brand_color: Mapped[str] = mapped_column(String(9), nullable=False, default="#0B0D14")
    accent_color: Mapped[str] = mapped_column(String(9), nullable=False, default="#FA8405")
    price_range: Mapped[str | None] = mapped_column(String(4))

    # Contacto y ubicación
    phone: Mapped[str | None] = mapped_column(String(40))
    whatsapp: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(12))
    city: Mapped[str | None] = mapped_column(String(100))
    province: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="ES")
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    google_place_id: Mapped[str | None] = mapped_column(String(255))
    google_maps_url: Mapped[str | None] = mapped_column(String(500))
    instagram: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(255))

    # Horario: {"mon": [["13:30", "24:00"]], "tue": [["19:00", "01:30"]], ...}
    # Un tramo que acaba antes de empezar cruza la medianoche.
    opening_hours: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Cierres puntuales: [{"from": "2026-12-24", "to": "2026-12-25", "reason": "Navidad"}]
    closures: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Hora a la que cambia el día de trabajo (cierran a la 1:30: el pedido de las 0:45 es del día anterior)
    day_change_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=6)

    # Pedidos
    ordering_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ordering_paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepts_scheduled_orders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dine_in_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    takeaway_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delivery_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    delivery_min_order: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    delivery_note: Mapped[str | None] = mapped_column(String(255))
    prep_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    payment_methods: Mapped[list] = mapped_column(JSONB, nullable=False, default=lambda: ["cash", "card"])

    # Contenido
    languages: Mapped[list] = mapped_column(JSONB, nullable=False, default=lambda: ["es", "en"])
    offer_text: Mapped[str | None] = mapped_column(String(280))
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allergen_notice: Mapped[str | None] = mapped_column(Text)
    # Ley 7/2022 de residuos: la hostelería debe ofrecer agua del grifo gratis
    free_tap_water: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class VenueFeedback(Base, TimestampMixin):
    """Comentario privado al dueño. Va con el mismo peso visual que el botón de
    reseña de Google (sin filtrar por estrellas, como exigen las normas de Google)."""

    __tablename__ = "venue_feedback"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    contact: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
