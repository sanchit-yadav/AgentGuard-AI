"""Organization, User, and Multi-Tenant RBAC Membership SQLAlchemy models."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Multi-tenant organization boundary entity.

    All projects, billing scopes, and agent evaluation data are partitioned
    by organization.
    """

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable organization display name",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        doc="URL-safe unique organization identifier slug",
    )

    # Relationships
    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User account entity for platform authentication and authorization."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        doc="Primary login email address (case-insensitive unique index)",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Bcrypt hashed account password",
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="User's full name",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the user account is active and permitted to authenticate",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the user email address has been verified",
    )

    # Relationships
    memberships: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OrganizationMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Association entity mapping users to organizations with assigned RBAC roles."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_members_org_user",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent organization",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to member user",
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default="MEMBER",
        nullable=False,
        doc="Assigned RBAC role: OWNER, ADMIN, MEMBER, or VIEWER",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")
