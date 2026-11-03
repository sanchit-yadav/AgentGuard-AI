"""Foundational SQLAlchemy 2.x declarative base and model mixins.

Provides:
- Base: DeclarativeBase with standardized constraint naming conventions.
- UUIDPrimaryKeyMixin: UUIDv4 primary key mapping.
- TimestampMixin: Timezone-aware created_at and updated_at audit timestamps.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Standardized PostgreSQL constraint naming convention to ensure deterministic
# constraint names for Alembic migrations and foreign key integrity.
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Abstract declarative base class for all AgentGuard database models."""

    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """Mixin adding an immutable UUIDv4 primary key column."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        sort_order=-100,
        doc="Unique primary key identifier (UUIDv4)",
    )


class TimestampMixin:
    """Mixin adding timezone-aware created_at and updated_at audit columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp of initial record creation (UTC)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp of most recent record update (UTC)",
    )
