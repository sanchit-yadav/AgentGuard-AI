"""TestRun and TestExecution batch orchestration SQLAlchemy models."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent import AgentVersion
    from app.models.evaluation import Evaluation, Report, SecurityFinding
    from app.models.project import Project
    from app.models.test_suite import TestCase, TestSuite
    from app.models.trace import ExecutionTrace


class TestRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Batch test suite execution against an immutable agent version."""

    __tablename__ = "test_runs"
    __table_args__ = (
        Index("ix_test_runs_project", "project_id", "created_at"),
        Index("ix_test_runs_suite", "test_suite_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent project workspace",
    )
    test_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to executed test suite",
    )
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Foreign key reference to pinned immutable agent version snapshot",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        doc="Run state: PENDING, RUNNING, COMPLETED, FAILED, or CANCELLED",
    )
    total_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Total number of test executions in this batch run",
    )
    passed_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of successfully passed test executions",
    )
    failed_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of failed or errored test executions",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Total elapsed execution duration in milliseconds",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when worker began executing the run",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when all executions in the run completed",
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="test_runs")
    test_suite: Mapped["TestSuite"] = relationship(back_populates="test_runs")
    agent_version: Mapped["AgentVersion"] = relationship(back_populates="test_runs")
    executions: Mapped[list["TestExecution"]] = relationship(
        back_populates="test_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="test_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TestExecution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Execution instance of a single test case within a test run."""

    __tablename__ = "test_executions"
    __table_args__ = (
        Index("ix_test_executions_run", "test_run_id"),
        Index("ix_test_executions_passed", "passed"),
        Index(
            "ix_test_executions_failure",
            "failure_category",
            postgresql_where="failure_category IS NOT NULL",
        ),
    )

    test_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent test run",
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Foreign key reference to executed test case specification",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        doc="State: PENDING, RUNNING, EVALUATING, COMPLETED, FAILED, or TIMEOUT",
    )
    passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        doc="Overall boolean pass/fail verdict (null while pending/running)",
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Total test case execution duration in milliseconds",
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Total tokens consumed across all model turns in this execution",
    )
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        default=Decimal("0.000000"),
        nullable=False,
        doc="Estimated USD token cost based on model provider pricing",
    )
    failure_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="RCA failure category: TOOL_SELECTION_ERROR, PARAMETER_TYPE_MISMATCH, etc.",
    )
    failure_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Concise diagnostic summary generated by Root Cause Analysis",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when execution and evaluations finished",
    )

    # Relationships
    test_run: Mapped["TestRun"] = relationship(back_populates="executions")
    test_case: Mapped["TestCase"] = relationship(back_populates="executions")
    trace: Mapped["ExecutionTrace | None"] = relationship(
        back_populates="test_execution",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="test_execution",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    security_findings: Mapped[list["SecurityFinding"]] = relationship(
        back_populates="test_execution",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
