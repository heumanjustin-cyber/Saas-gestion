from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.employee import Employee
    from app.models.membership import CompanyMembership


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    companies: Mapped[list["Company"]] = relationship(
        "Company",
        back_populates="owner",
    )

    memberships: Mapped[list["CompanyMembership"]] = relationship(
        "CompanyMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    employee_profile: Mapped["Employee | None"] = relationship(
        "Employee",
        back_populates="user",
        uselist=False,
    )