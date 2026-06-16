from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CompanySettings(Base, TimestampMixin):
    __tablename__ = "company_settings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    business_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="hair_salon",
    )

    whatsapp_number: Mapped[str | None] = mapped_column(
        String(50)
    )

    instagram_username: Mapped[str | None] = mapped_column(
        String(100)
    )

    website: Mapped[str | None] = mapped_column(
        String(255)
    )

    online_booking_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    ai_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    automatic_reminders: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )