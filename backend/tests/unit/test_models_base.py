"""Unit tests for foundational SQLAlchemy models, mixins, and naming conventions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Index, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import (
    POSTGRES_NAMING_CONVENTION,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ConcreteItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Concrete model for verifying Base and mixin behavior."""

    __tablename__ = "test_items"

    __table_args__ = (
        UniqueConstraint("created_at", name="uq_test_items_created_at"),
        Index("ix_test_items_created_at", "created_at"),
    )


def test_postgres_naming_convention_present_on_base_metadata() -> None:
    """Verify that Base.metadata includes the standardized PostgreSQL naming conventions."""
    assert Base.metadata.naming_convention == POSTGRES_NAMING_CONVENTION
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
    assert (
        Base.metadata.naming_convention["fk"]
        == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    )
    assert (
        Base.metadata.naming_convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    )
    assert (
        Base.metadata.naming_convention["ck"] == "ck_%(table_name)s_%(constraint_name)s"
    )
    assert Base.metadata.naming_convention["ix"] == "ix_%(column_0_label)s"


def test_uuid_primary_key_mixin_columns() -> None:
    """Verify that UUIDPrimaryKeyMixin defines a non-nullable primary key UUID column."""
    table = ConcreteItem.__table__
    id_col = table.c.id

    assert id_col.primary_key is True
    assert id_col.nullable is False
    assert isinstance(id_col.type, UUID)
    assert id_col.type.as_uuid is True

    # Test default generator creates valid UUIDv4
    assert id_col.default is not None
    generated_uuid = id_col.default.arg(None)
    assert isinstance(generated_uuid, uuid.UUID)
    assert generated_uuid.version == 4


def test_timestamp_mixin_columns() -> None:
    """Verify created_at and updated_at columns are timezone-aware and non-nullable."""
    table = ConcreteItem.__table__
    created_at_col = table.c.created_at
    updated_at_col = table.c.updated_at

    assert created_at_col.nullable is False
    assert updated_at_col.nullable is False
    assert created_at_col.server_default is not None
    assert updated_at_col.server_default is not None

    # Verify python default generators produce UTC timezone-aware datetimes
    assert created_at_col.default is not None
    assert updated_at_col.default is not None

    now_created = created_at_col.default.arg(None)
    now_updated = updated_at_col.default.arg(None)

    assert isinstance(now_created, datetime)
    assert isinstance(now_updated, datetime)
    assert now_created.tzinfo == UTC
    assert now_updated.tzinfo == UTC


def test_model_instantiation_with_explicit_values() -> None:
    """Verify that models accept explicit attribute assignments during instantiation."""
    explicit_id = uuid.uuid4()
    custom_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

    item = ConcreteItem(
        id=explicit_id,
        created_at=custom_time,
        updated_at=custom_time,
    )

    assert item.id == explicit_id
    assert item.created_at == custom_time
    assert item.updated_at == custom_time


def test_table_constraint_naming() -> None:
    """Verify that table constraints follow the configured naming convention."""
    table = ConcreteItem.__table__
    assert isinstance(table.primary_key, PrimaryKeyConstraint)
    assert table.primary_key.name == "pk_test_items"
