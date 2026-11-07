"""Project workspace entity scoping agents, test suites, and evaluation runs."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.test_run import TestRun
    from app.models.test_suite import TestSuite
    from app.models.user import Organization


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Logical project workspace scoping target agents, test suites, and runs."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_projects_org_slug"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent organization",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable project workspace name",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="URL-safe project identifier slug, unique per organization",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional project description and guidelines",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="projects")
    agents: Mapped[list["Agent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    test_suites: Mapped[list["TestSuite"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    test_runs: Mapped[list["TestRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
