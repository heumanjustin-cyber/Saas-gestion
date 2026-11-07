"""Pedidos: los que entran por QR/web y los que se toman en el TPV.

El precio lo calcula siempre el servidor a partir de la carta (nunca se fía
del precio que manda el móvil), y el número del día es correlativo: 1, 2, 3...
sin las colisiones de los códigos aleatorios de 4 cifras.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

ORDER_STATUSES = ("pending", "accepted", "preparing", "ready", "completed", "rejected", "cancelled")
FINAL_STATUSES = ("completed", "rejected", "cancelled")
FULFILLMENTS = ("dine_in", "takeaway", "delivery")

# Transiciones permitidas para el personal (cocina, barra, TPV)
STAFF_TRANSITIONS = {
    "pending": {"accepted", "rejected", "preparing", "ready", "cancelled"},
    "accepted": {"preparing", "ready", "cancelled"},
    "preparing": {"ready", "cancelled"},
    "ready": {"completed", "preparing"},
    "completed": set(),
    "rejected": set(),
    "cancelled": set(),
}


class SequenceCounter(Base):
    """Contador atómico por empresa y ámbito (pedidos del día, series de facturas, cierres Z).

    Se incrementa con INSERT ... ON CONFLICT DO UPDATE ... RETURNING: la fila queda
    bloqueada hasta el commit, así que dos cajas a la vez nunca sacan el mismo número
    y, si la transacción falla, el número no se gasta (sin huecos en la serie).
    """

    __tablename__ = "sequence_counters"

    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("company_id", "business_date", "number", name="uq_orders_daily_number"),
        UniqueConstraint("company_id", "client_ref", name="uq_orders_client_ref"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    public_token: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    # Reintento del mismo pedido (doble toque, red que falla): misma referencia → mismo pedido
    client_ref: Mapped[str | None] = mapped_column(String(64))

    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="web")  # qr, web, pos, phone
    fulfillment: Mapped[str] = mapped_column(String(20), nullable=False, default="takeaway")
    table_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("dining_tables.id", ondelete="SET NULL")
    )
    table_label: Mapped[str | None] = mapped_column(String(60))
    qr_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("qr_codes.id", ondelete="SET NULL"))

    customer_name: Mapped[str | None] = mapped_column(String(120))
    customer_phone: Mapped[str | None] = mapped_column(String(40))
    delivery_address: Mapped[str | None] = mapped_column(String(255))
    customer_note: Mapped[str | None] = mapped_column(String(280))
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="es")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    status_reason: Mapped[str | None] = mapped_column(String(255))
    estimated_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    payment_method: Mapped[str | None] = mapped_column(String(20))  # lo que dice que pagará
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid")
    invoice_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), index=True
    )

    lines: Mapped[list["OrderLine"]] = relationship(
        "OrderLine", back_populates="order", order_by="OrderLine.position", cascade="all, delete-orphan"
    )

    @property
    def display_number(self) -> str:
        return f"{self.number:03d}"


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("menu_products.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(150), nullable=False)  # copia: la carta puede cambiar mañana
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("10"))
    modifiers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # [{group, name, price_delta}]
    removed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # ["Sin cebolla"]
    note: Mapped[str | None] = mapped_column(Text)
    kitchen_station: Mapped[str | None] = mapped_column(String(40))

    order: Mapped["Order"] = relationship("Order", back_populates="lines")
