"""Esquemas de entrada de hostelería: local, carta, mesas/QR, pedidos y TPV."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.services.allergens import ALLERGENS, normalize_allergens
from app.services.hours import validate_hours

HexColor = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
Lang = Literal["es", "en", "fr"]


def _check_allergens(values: list[str]) -> list[str]:
    out = normalize_allergens(values)
    unknown = [v for v in values if normalize_allergens([v]) == []]
    if unknown:
        raise ValueError(f"Alérgeno desconocido: {unknown[0]!r}. Válidos: {', '.join(ALLERGENS)}")
    return out


# ---------------------------------------------------------------- local
class VenueProfileIn(BaseModel):
    display_name: str | None = Field(None, max_length=150)
    tagline: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    cuisine: list[str] | None = None
    tags: list[str] | None = None
    logo_url: str | None = Field(None, max_length=500)
    cover_url: str | None = Field(None, max_length=500)
    brand_color: str | None = HexColor
    accent_color: str | None = HexColor
    price_range: str | None = Field(None, pattern=r"^€{1,4}$")
    phone: str | None = Field(None, max_length=40)
    whatsapp: str | None = Field(None, max_length=40)
    email: str | None = Field(None, max_length=255)
    address: str | None = Field(None, max_length=255)
    postal_code: str | None = Field(None, max_length=12)
    city: str | None = Field(None, max_length=100)
    province: str | None = Field(None, max_length=100)
    country: str | None = Field(None, min_length=2, max_length=2)
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)
    google_place_id: str | None = Field(None, max_length=255)
    google_maps_url: str | None = Field(None, max_length=500)
    instagram: str | None = Field(None, max_length=100)
    website: str | None = Field(None, max_length=255)
    opening_hours: dict | None = None
    closures: list[dict] | None = None
    day_change_hour: int | None = Field(None, ge=0, le=12)
    ordering_enabled: bool | None = None
    accepts_scheduled_orders: bool | None = None
    dine_in_enabled: bool | None = None
    takeaway_enabled: bool | None = None
    delivery_enabled: bool | None = None
    delivery_fee: Decimal | None = Field(None, ge=0, le=100)
    delivery_min_order: Decimal | None = Field(None, ge=0, le=1000)
    delivery_note: str | None = Field(None, max_length=255)
    prep_time_minutes: int | None = Field(None, ge=1, le=180)
    payment_methods: list[Literal["cash", "card", "bizum"]] | None = None
    languages: list[Lang] | None = None
    offer_text: str | None = Field(None, max_length=280)
    offer_expires_at: datetime | None = None
    allergen_notice: str | None = Field(None, max_length=2000)
    free_tap_water: bool | None = None
    is_published: bool | None = None

    @field_validator("opening_hours")
    @classmethod
    def _hours(cls, v):
        return validate_hours(v) if v is not None else v


class FiscalProfileIn(BaseModel):
    nif: str = Field(..., min_length=9, max_length=20)
    legal_name: str = Field(..., min_length=2, max_length=150)
    address: str | None = Field(None, max_length=255)
    postal_code: str | None = Field(None, max_length=12)
    city: str | None = Field(None, max_length=100)
    province: str | None = Field(None, max_length=100)
    verifactu_enabled: bool = False
    environment: Literal["test", "production"] = "test"
    ticket_footer: str | None = Field(None, max_length=255)


# ---------------------------------------------------------------- carta
class CategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    note: str | None = Field(None, max_length=255)
    image_url: str | None = Field(None, max_length=500)
    position: int = 0
    is_active: bool = True
    i18n: dict = Field(default_factory=dict)
    suggest_category_id: UUID | None = None


class CategoryPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=2000)
    note: str | None = Field(None, max_length=255)
    image_url: str | None = Field(None, max_length=500)
    position: int | None = None
    is_active: bool | None = None
    i18n: dict | None = None
    suggest_category_id: UUID | None = None


class OptionIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    price_delta: Decimal = Field(Decimal("0"), ge=-100, le=100)
    allergens: list[str] = Field(default_factory=list)
    is_available: bool = True
    is_default: bool = False
    i18n: dict = Field(default_factory=dict)

    @field_validator("allergens")
    @classmethod
    def _allergens(cls, v):
        return _check_allergens(v)


class GroupIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    min_select: int = Field(0, ge=0, le=20)
    max_select: int = Field(1, ge=0, le=20)  # 0 = sin límite
    position: int = 0
    i18n: dict = Field(default_factory=dict)
    options: list[OptionIn] = Field(default_factory=list)


class ProductIn(BaseModel):
    category_id: UUID
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(None, max_length=2000)
    price: Decimal = Field(..., ge=0, le=10000)
    tax_rate: Decimal = Field(Decimal("10"), ge=0, le=21)
    takeaway_tax_rate: Decimal | None = Field(None, ge=0, le=21)
    image_url: str | None = Field(None, max_length=500)
    allergens: list[str] = Field(default_factory=list)
    may_contain: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    removable_ingredients: list[str] = Field(default_factory=list)
    is_available: bool = True
    is_active: bool = True
    position: int = 0
    i18n: dict = Field(default_factory=dict)
    upsell_product_id: UUID | None = None
    kitchen_station: str | None = Field(None, max_length=40)
    sku: str | None = Field(None, max_length=60)
    group_ids: list[UUID] = Field(default_factory=list)

    @field_validator("allergens", "may_contain")
    @classmethod
    def _allergens(cls, v):
        return _check_allergens(v)


class ProductPatch(BaseModel):
    category_id: UUID | None = None
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=2000)
    price: Decimal | None = Field(None, ge=0, le=10000)
    tax_rate: Decimal | None = Field(None, ge=0, le=21)
    takeaway_tax_rate: Decimal | None = Field(None, ge=0, le=21)
    image_url: str | None = Field(None, max_length=500)
    allergens: list[str] | None = None
    may_contain: list[str] | None = None
    tags: list[str] | None = None
    removable_ingredients: list[str] | None = None
    is_available: bool | None = None
    is_active: bool | None = None
    position: int | None = None
    i18n: dict | None = None
    upsell_product_id: UUID | None = None
    kitchen_station: str | None = Field(None, max_length=40)
    sku: str | None = Field(None, max_length=60)
    group_ids: list[UUID] | None = None

    @field_validator("allergens", "may_contain")
    @classmethod
    def _allergens(cls, v):
        return _check_allergens(v) if v is not None else v


class AvailabilityIn(BaseModel):
    is_available: bool


# ---------------------------------------------------------------- mesas y QR
class TableIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    zone: str | None = Field(None, max_length=60)
    seats: int | None = Field(None, ge=1, le=50)
    position: int = 0
    is_active: bool = True


class TablesBulkIn(BaseModel):
    """Crea N mesas con su QR de golpe: «Mesa 1» ... «Mesa N»."""

    count: int = Field(..., ge=1, le=100)
    prefix: str = Field("Mesa", max_length=40)
    zone: str | None = Field(None, max_length=60)
    start_at: int = Field(1, ge=1, le=999)


class QrIn(BaseModel):
    kind: Literal["table", "counter", "display", "keychain", "door", "bag", "flyer", "other"] = "counter"
    label: str | None = Field(None, max_length=120)
    table_id: UUID | None = None
    target: Literal["menu", "review", "url"] = "menu"
    target_url: str | None = Field(None, max_length=500, pattern=r"^https://")
    campaign: str | None = Field(None, max_length=60)


class QrPatch(BaseModel):
    label: str | None = Field(None, max_length=120)
    target: Literal["menu", "review", "url"] | None = None
    target_url: str | None = Field(None, max_length=500, pattern=r"^https://")
    campaign: str | None = Field(None, max_length=60)
    is_active: bool | None = None


# ---------------------------------------------------------------- pedidos
class OrderLineIn(BaseModel):
    product_id: UUID
    quantity: int = Field(1, ge=1, le=50)
    option_ids: list[UUID] = Field(default_factory=list, max_length=30)
    removed: list[str] = Field(default_factory=list, max_length=20)
    note: str | None = Field(None, max_length=140)


class PublicOrderIn(BaseModel):
    client_ref: str = Field(..., min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    fulfillment: Literal["dine_in", "takeaway", "delivery"]
    qr_code: str | None = Field(None, max_length=16)
    customer_name: str | None = Field(None, max_length=120)
    customer_phone: str | None = Field(None, max_length=40)
    delivery_address: str | None = Field(None, max_length=255)
    customer_note: str | None = Field(None, max_length=280)
    scheduled_for: datetime | None = None
    payment_method: Literal["cash", "card", "bizum"] | None = None
    language: Lang = "es"
    lines: list[OrderLineIn] = Field(..., min_length=1, max_length=40)
    website: str | None = Field(None, max_length=200)  # trampa para bots: un humano lo deja vacío


class StatusChangeIn(BaseModel):
    status: Literal["accepted", "preparing", "ready", "completed", "rejected", "cancelled"]
    reason: str | None = Field(None, max_length=255)
    eta_minutes: int | None = Field(None, ge=1, le=240)


class PauseIn(BaseModel):
    minutes: int = Field(..., ge=0, le=480)  # 0 = reanudar


class OfferIn(BaseModel):
    text: str | None = Field(None, max_length=280)
    hours: int | None = Field(None, ge=1, le=168)  # caduca sola


class FeedbackIn(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)
    contact: str | None = Field(None, max_length=255)
    order_token: str | None = Field(None, max_length=40)
    website: str | None = Field(None, max_length=200)


# ---------------------------------------------------------------- TPV
class RegisterIn(BaseModel):
    name: str = Field("Caja 1", min_length=1, max_length=80)
    ticket_prefix: str = Field("T1", pattern=r"^[A-Z0-9]{1,6}$")
    invoice_prefix: str = Field("F1", pattern=r"^[A-Z0-9]{1,6}$")
    refund_prefix: str = Field("R1", pattern=r"^[A-Z0-9]{1,6}$")


class PairingCodeIn(BaseModel):
    register_id: UUID
    device_name: str | None = Field(None, max_length=80)


class PairIn(BaseModel):
    code: str = Field(..., min_length=6, max_length=12)
    device_name: str | None = Field(None, max_length=80)


class StaffPinIn(BaseModel):
    employee_id: UUID
    pin: str = Field(..., pattern=r"^\d{4,6}$")
    role: Literal["cashier", "manager"] = "cashier"


class PinLoginIn(BaseModel):
    employee_id: UUID
    pin: str = Field(..., pattern=r"^\d{4,6}$")


class OwnerSessionIn(BaseModel):
    register_id: UUID


class OpenSessionIn(BaseModel):
    opening_float: Decimal = Field(Decimal("0"), ge=0, le=100000)


class MovementIn(BaseModel):
    kind: Literal["in", "out"]
    amount: Decimal = Field(..., gt=0, le=100000)
    reason: str = Field(..., min_length=2, max_length=255)


class CloseSessionIn(BaseModel):
    breakdown: dict[str, int] | None = None
    counted_cash: Decimal | None = Field(None, ge=0, le=1000000)
    notes: str | None = Field(None, max_length=1000)


class SaleLineIn(BaseModel):
    product_id: UUID | None = None
    description: str | None = Field(None, max_length=200)  # artículo libre («Varios»)
    unit_price: Decimal | None = Field(None, ge=0, le=10000)
    tax_rate: Decimal = Field(Decimal("10"), ge=0, le=21)
    quantity: int = Field(1, ge=1, le=999)
    option_ids: list[UUID] = Field(default_factory=list, max_length=30)
    removed: list[str] = Field(default_factory=list, max_length=20)
    note: str | None = Field(None, max_length=140)


class PaymentSchema(BaseModel):
    method: Literal["cash", "card", "bizum", "other"]
    amount: Decimal = Field(..., gt=0, le=100000)
    tendered: Decimal | None = Field(None, gt=0, le=100000)
    reference: str | None = Field(None, max_length=80)


class SaleIn(BaseModel):
    lines: list[SaleLineIn] = Field(default_factory=list, max_length=200)
    order_ids: list[UUID] = Field(default_factory=list, max_length=20)
    payments: list[PaymentSchema] = Field(..., min_length=1, max_length=5)
    fulfillment: Literal["dine_in", "takeaway", "delivery"] = "dine_in"
    table_label: str | None = Field(None, max_length=60)
    customer_name: str | None = Field(None, max_length=120)
    send_to_kitchen: bool = True
    note: str | None = Field(None, max_length=280)


class RefundItemIn(BaseModel):
    line_id: UUID
    quantity: Decimal = Field(..., gt=0, le=999)


class RefundIn(BaseModel):
    items: list[RefundItemIn] | None = None  # vacío = devolución total
    method: Literal["cash", "card", "bizum", "other"] = "cash"
    reason: str = Field(..., min_length=3, max_length=255)


class VoidIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=255)


class FullInvoiceIn(BaseModel):
    invoice_ids: list[UUID] = Field(..., min_length=1, max_length=20)
    nif: str = Field(..., min_length=9, max_length=20)
    name: str = Field(..., min_length=2, max_length=150)
    address: str | None = Field(None, max_length=255)
