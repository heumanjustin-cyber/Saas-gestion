"""TPV: cajas, dispositivos emparejados, PIN del personal, sesiones de caja y facturas.

Las facturas (tickets) no se editan ni se borran: una devolución es una
factura rectificativa (R5) y una factura completa a petición del cliente es
una F3 que sustituye al ticket. Así lo exige el Reglamento de sistemas de
facturación (RD 1007/2023, «Verifactu»).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

PAYMENT_METHODS = ("cash", "card", "bizum", "other")
INVOICE_TYPES = ("F1", "F2", "F3", "R5")


class PosRegister(Base, TimestampMixin):
    """Una caja (punto de cobro) con sus series de numeración."""

    __tablename__ = "pos_registers"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="Caja 1")
    # Series: tickets (F2), facturas completas (F1/F3) y rectificativas (R5) en series separadas
    ticket_prefix: Mapped[str] = mapped_column(String(10), nullable=False, default="T1")
    invoice_prefix: Mapped[str] = mapped_column(String(10), nullable=False, default="F1")
    refund_prefix: Mapped[str] = mapped_column(String(10), nullable=False, default="R1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PosPairingCode(Base, TimestampMixin):
    """Código de un solo uso (15 min) para emparejar una tablet o TPV con una caja."""

    __tablename__ = "pos_pairing_codes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    register_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pos_registers.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PosDevice(Base, TimestampMixin):
    __tablename__ = "pos_devices"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    register_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pos_registers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="TPV")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StaffPin(Base, TimestampMixin):
    """PIN de 4-6 cifras de un empleado para el TPV. Solo sirve desde un dispositivo emparejado."""

    __tablename__ = "pos_staff_pins"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    pin_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    pin_salt: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="cashier")  # cashier | manager
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CashSession(Base, TimestampMixin):
    """Turno de caja: apertura con fondo, arqueo y cierre Z."""

    __tablename__ = "cash_sessions"
    __table_args__ = (
        # Una sola sesión abierta por caja
        Index(
            "uq_cash_sessions_one_open",
            "register_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    register_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pos_registers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opened_by: Mapped[str] = mapped_column(String(120), nullable=False)
    opening_float: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(120))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    counted_breakdown: Mapped[dict | None] = mapped_column(JSONB)  # {"50": 2, "20": 3, "0.5": 4}
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    z_number: Mapped[int | None] = mapped_column(Integer)
    z_report: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)


class CashMovement(Base, TimestampMixin):
    """Entrada o salida de efectivo que no es una venta (cambio, pago a proveedor...)."""

    __tablename__ = "cash_movements"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cash_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(5), nullable=False)  # in | out
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("company_id", "series", "number", name="uq_invoices_series_number"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    register_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pos_registers.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cash_sessions.id", ondelete="SET NULL"), index=True
    )
    invoice_type: Mapped[str] = mapped_column(String(2), nullable=False, default="F2")
    series: Mapped[str] = mapped_column(String(30), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    full_number: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="issued")  # issued | voided

    fulfillment: Mapped[str | None] = mapped_column(String(20))
    channel: Mapped[str | None] = mapped_column(String(20))
    table_label: Mapped[str | None] = mapped_column(String(60))
    customer_nif: Mapped[str | None] = mapped_column(String(20))
    customer_name: Mapped[str | None] = mapped_column(String(150))
    customer_address: Mapped[str | None] = mapped_column(String(255))

    tax_base: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_breakdown: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # [{rate, base, tax}]

    rectified_invoice_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT")
    )
    substituted_invoice_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)

    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine", back_populates="invoice", order_by="InvoiceLine.position", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="invoice", order_by="Payment.created_at", cascade="all, delete-orphan"
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Sin clave foránea a propósito: la línea es historia fiscal inalterable y el plato puede
    # borrarse de la carta mañana (un SET NULL reescribiría la factura).
    product_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), index=True)
    category_name: Mapped[str | None] = mapped_column(String(120))
    # En una devolución (R5): la línea del ticket original que se devuelve
    source_line_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoice_lines.id", ondelete="RESTRICT")
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # IVA incluido
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # IVA incluido

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cash_sessions.id", ondelete="SET NULL"), index=True
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  # negativo en devoluciones
    tendered: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # lo que entrega en efectivo
    change_given: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    reference: Mapped[str | None] = mapped_column(String(80))  # datáfono / Bizum
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")


class AuditEvent(Base):
    """Registro de eventos del sistema de facturación (apertura, cierre Z, anulaciones...)."""

    __tablename__ = "pos_audit_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
