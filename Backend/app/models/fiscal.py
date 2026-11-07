"""Registros de facturación encadenados (RD 1007/2023 y Orden HAC/1177/2024, «Verifactu»).

Cada factura emitida genera un registro de alta; cada anulación, un registro de
anulación. Cada registro lleva la huella SHA-256 del anterior del mismo emisor,
de modo que no se puede quitar ni cambiar un ticket sin romper la cadena.

La base de datos lo refuerza: un trigger impide borrar registros, facturas,
líneas y pagos, y cambiar los campos que entran en la huella.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DDL, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, event, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.pos import Invoice, InvoiceLine, Payment


class FiscalProfile(Base, TimestampMixin):
    """Datos fiscales del obligado a expedir factura (el restaurante)."""

    __tablename__ = "fiscal_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    nif: Mapped[str] = mapped_column(String(20), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(12))
    city: Mapped[str | None] = mapped_column(String(100))
    province: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="ES")
    # Remisión a la AEAT: desactivada hasta tener certificado y alta del SIF
    verifactu_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    environment: Mapped[str] = mapped_column(String(12), nullable=False, default="test")  # test | production
    ticket_footer: Mapped[str | None] = mapped_column(String(255))


class FiscalChainHead(Base):
    """Último eslabón de la cadena de cada emisor. Se bloquea (FOR UPDATE) al emitir."""

    __tablename__ = "fiscal_chain_heads"

    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_hash: Mapped[str | None] = mapped_column(String(64))
    last_nif: Mapped[str | None] = mapped_column(String(20))
    last_num_serie: Mapped[str | None] = mapped_column(String(60))
    last_fecha: Mapped[str | None] = mapped_column(String(10))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FiscalRecord(Base):
    __tablename__ = "fiscal_records"
    __table_args__ = (UniqueConstraint("company_id", "sequence", name="uq_fiscal_records_sequence"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    record_type: Mapped[str] = mapped_column(String(10), nullable=False)  # alta | anulacion
    invoice_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    issuer_nif: Mapped[str] = mapped_column(String(20), nullable=False)
    num_serie: Mapped[str] = mapped_column(String(60), nullable=False)
    fecha_expedicion: Mapped[str] = mapped_column(String(10), nullable=False)  # DD-MM-AAAA
    tipo_factura: Mapped[str | None] = mapped_column(String(2))
    cuota_total: Mapped[str | None] = mapped_column(String(20))
    importe_total: Mapped[str | None] = mapped_column(String(20))
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    generated_at: Mapped[str] = mapped_column(String(30), nullable=False)  # FechaHoraHusoGenRegistro
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    qr_url: Mapped[str | None] = mapped_column(String(500))
    environment: Mapped[str] = mapped_column(String(12), nullable=False, default="test")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Estado de la remisión a la AEAT (lo único que cambia después de crear el registro)
    submission_status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    submission_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    aeat_csv: Mapped[str | None] = mapped_column(String(64))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Inalterabilidad en la propia base de datos (Postgres)
# ---------------------------------------------------------------------------
_FISCAL_GUARD = DDL(
    """
CREATE OR REPLACE FUNCTION buhos_fiscal_records_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BUHOS: los registros de facturación no se pueden borrar';
  END IF;
  IF NEW.hash IS DISTINCT FROM OLD.hash
     OR NEW.previous_hash IS DISTINCT FROM OLD.previous_hash
     OR NEW.sequence IS DISTINCT FROM OLD.sequence
     OR NEW.payload IS DISTINCT FROM OLD.payload
     OR NEW.generated_at IS DISTINCT FROM OLD.generated_at
     OR NEW.invoice_id IS DISTINCT FROM OLD.invoice_id
     OR NEW.num_serie IS DISTINCT FROM OLD.num_serie
     OR NEW.importe_total IS DISTINCT FROM OLD.importe_total
     OR NEW.cuota_total IS DISTINCT FROM OLD.cuota_total THEN
    RAISE EXCEPTION 'BUHOS: los registros de facturación son inalterables';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_buhos_fiscal_records_guard
  BEFORE UPDATE OR DELETE ON fiscal_records
  FOR EACH ROW EXECUTE FUNCTION buhos_fiscal_records_guard();
"""
).execute_if(dialect="postgresql")

_INVOICE_GUARD = DDL(
    """
CREATE OR REPLACE FUNCTION buhos_invoices_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BUHOS: una factura emitida no se borra: se rectifica o se anula';
  END IF;
  IF NEW.series IS DISTINCT FROM OLD.series
     OR NEW.number IS DISTINCT FROM OLD.number
     OR NEW.full_number IS DISTINCT FROM OLD.full_number
     OR NEW.invoice_type IS DISTINCT FROM OLD.invoice_type
     OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
     OR NEW.total IS DISTINCT FROM OLD.total
     OR NEW.tax_total IS DISTINCT FROM OLD.tax_total
     OR NEW.tax_base IS DISTINCT FROM OLD.tax_base
     OR NEW.tax_breakdown IS DISTINCT FROM OLD.tax_breakdown THEN
    RAISE EXCEPTION 'BUHOS: una factura emitida no se modifica';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_buhos_invoices_guard
  BEFORE UPDATE OR DELETE ON invoices
  FOR EACH ROW EXECUTE FUNCTION buhos_invoices_guard();
"""
).execute_if(dialect="postgresql")

_IMMUTABLE_ROW_FN = """
CREATE OR REPLACE FUNCTION buhos_immutable_row_guard() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BUHOS: las líneas y los pagos de una factura emitida no se modifican';
END $$ LANGUAGE plpgsql;
"""

# Cada DDL define la función por si la otra tabla aún no existe (create_all no garantiza el orden)
_LINES_GUARD = DDL(
    _IMMUTABLE_ROW_FN
    + """
CREATE TRIGGER trg_buhos_invoice_lines_guard
  BEFORE UPDATE OR DELETE ON invoice_lines
  FOR EACH ROW EXECUTE FUNCTION buhos_immutable_row_guard();
"""
).execute_if(dialect="postgresql")

_PAYMENTS_GUARD = DDL(
    _IMMUTABLE_ROW_FN
    + """
CREATE TRIGGER trg_buhos_payments_guard
  BEFORE UPDATE OR DELETE ON payments
  FOR EACH ROW EXECUTE FUNCTION buhos_immutable_row_guard();
"""
).execute_if(dialect="postgresql")

event.listen(FiscalRecord.__table__, "after_create", _FISCAL_GUARD)
event.listen(Invoice.__table__, "after_create", _INVOICE_GUARD)
event.listen(InvoiceLine.__table__, "after_create", _LINES_GUARD)
event.listen(Payment.__table__, "after_create", _PAYMENTS_GUARD)
