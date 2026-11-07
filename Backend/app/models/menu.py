"""Carta digital: categorías, platos y modificadores (carne, salsa, extras...).

Cada plato guarda sus alérgenos con los 14 códigos del Reglamento (UE)
1169/2011 (ver app/services/allergens.py), no una nota genérica.
`i18n` guarda las traducciones: {"en": {"name": "...", "description": "..."}}.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


product_modifier_groups = Table(
    "menu_product_modifier_groups",
    Base.metadata,
    Column("product_id", PG_UUID(as_uuid=True), ForeignKey("menu_products.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", PG_UUID(as_uuid=True), ForeignKey("menu_modifier_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("position", Integer, nullable=False, default=0),
)


class MenuCategory(Base, TimestampMixin):
    __tablename__ = "menu_categories"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    i18n: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Al añadir un plato de esta categoría se sugieren los de otra (p. ej. bebidas)
    suggest_category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("menu_categories.id", ondelete="SET NULL")
    )
    external_ref: Mapped[str | None] = mapped_column(String(80))

    products: Mapped[list["MenuProduct"]] = relationship(
        "MenuProduct", back_populates="category", order_by="MenuProduct.position", cascade="all, delete-orphan"
    )


class MenuProduct(Base, TimestampMixin):
    __tablename__ = "menu_products"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("menu_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Precio final con IVA incluido (en España el consumidor ve siempre el precio final)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("10"))
    # Tipo distinto para llevar/domicilio (p. ej. refresco azucarado cerrado: 21 %). Lo decide la gestoría.
    takeaway_tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    image_url: Mapped[str | None] = mapped_column(String(500))
    allergens: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    may_contain: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # trazas
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # popular, nuevo, picante, vegano...
    removable_ingredients: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # «Sin cebolla»
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # False = agotado hoy
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # False = oculto
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    i18n: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # «¿Lo hacemos menú?»: plato al que se ofrece pasar con las mismas elecciones
    upsell_product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("menu_products.id", ondelete="SET NULL")
    )
    kitchen_station: Mapped[str | None] = mapped_column(String(40))
    sku: Mapped[str | None] = mapped_column(String(60))
    external_ref: Mapped[str | None] = mapped_column(String(80), index=True)

    category: Mapped["MenuCategory"] = relationship("MenuCategory", back_populates="products")
    modifier_groups: Mapped[list["ModifierGroup"]] = relationship(
        "ModifierGroup",
        secondary=product_modifier_groups,
        order_by=product_modifier_groups.c.position,
    )


class ModifierGroup(Base, TimestampMixin):
    """Grupo de elección: «Carne» (elige 1), «Extras» (elige 0 a 4)..."""

    __tablename__ = "menu_modifier_groups"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    min_select: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_select: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    i18n: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    external_ref: Mapped[str | None] = mapped_column(String(80))

    options: Mapped[list["ModifierOption"]] = relationship(
        "ModifierOption", back_populates="group", order_by="ModifierOption.position", cascade="all, delete-orphan"
    )


class ModifierOption(Base, TimestampMixin):
    __tablename__ = "menu_modifier_options"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    group_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("menu_modifier_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price_delta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    allergens: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    i18n: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    group: Mapped["ModifierGroup"] = relationship("ModifierGroup", back_populates="options")
