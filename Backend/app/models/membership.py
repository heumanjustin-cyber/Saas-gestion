from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User
    from app.models.role import Role


membership_roles = Table(
    "membership_roles",
    Base.metadata,
    Column(
        "membership_id",
        PG_UUID(as_uuid=True),
        ForeignKey(
            "company_memberships.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    Column(
        "role_id",
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class CompanyMembership(
    Base,
    TimestampMixin
):
    __tablename__ = "company_memberships"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    company_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    is_owner: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="memberships",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="memberships",
    )

    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=membership_roles,
        back_populates="memberships",
    )