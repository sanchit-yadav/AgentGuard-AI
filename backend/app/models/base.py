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
    """Mixin adding a UUIDv4 primary key column.

    Architecture & Immutability Semantics:
    - UUID Generation: Employs dual-tier generation. Python-side `default=uuid.uuid4`
      ensures the entity ID is known in memory immediately upon instantiation
      before flushing (crucial for domain events, child associations, and logging).
      PostgreSQL-side `server_default=func.gen_random_uuid()` ensures that direct
      SQL or external inserts also receive a cryptographically secure UUIDv4.
    - Primary Key Constraint: Enforces uniqueness and non-nullability, indexed
      under the deterministic name `pk_<tablename>`.
    - Immutability: The ID is treated as immutable at the application layer
      (domain models provide no mutation interfaces for primary keys). Note that
      SQLAlchemy does not enforce immutability at the physical database layer;
      preventing out-of-band direct SQL updates would require a database trigger.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        nullable=False,
        sort_order=-100,
        doc="Unique primary key identifier (UUIDv4)",
    )


class TimestampMixin:
    """Mixin adding timezone-aware created_at and updated_at audit columns.

    Architecture & Update Semantics:
    - created_at: Recorded in UTC at instantiation time via Python-side
      `default=lambda: datetime.now(UTC)` and server-side `server_default=func.now()`.
    - updated_at: Initialized at creation and automatically refreshed during
      SQLAlchemy ORM session flushes via `onupdate=lambda: datetime.now(UTC)`.
    - Database Trigger Caveat: SQLAlchemy's `onupdate` hook executes exclusively
      within the Python ORM runtime when an entity's attributes are modified and
      flushed. It is NOT equivalent to a PostgreSQL database-level `BEFORE UPDATE`
      trigger and will NOT automatically fire on direct raw SQL statements
      (e.g., bulk `UPDATE` statements executed outside the ORM unit-of-work).
    """

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
