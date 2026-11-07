"""TestSuite and TestCase specification SQLAlchemy models."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.test_run import TestExecution, TestRun


class TestSuite(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Curated collection of test scenarios evaluating an agent capability."""

    __tablename__ = "test_suites"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent project workspace",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable test suite title",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Description of test suite scope and evaluation goals",
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="test_suites")
    test_cases: Mapped[list["TestCase"]] = relationship(
        back_populates="test_suite",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    test_runs: Mapped[list["TestRun"]] = relationship(
        back_populates="test_suite",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TestCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Comprehensive test scenario specification."""

    __tablename__ = "test_cases"

    test_suite_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent test suite",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Descriptive test case title",
    )
    test_type: Mapped[str] = mapped_column(
        String(50),
        default="FUNCTIONAL",
        nullable=False,
        index=True,
        doc="Evaluation category: FUNCTIONAL, TOOL_VALIDATION, SECURITY, RELIABILITY, PERFORMANCE",
    )
    conversation_turns: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        doc="Multi-turn conversation script inputs: [{'role': 'user', 'content': '...'}]",
    )
    expected_outcome: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        doc="Expected terminal outcome: status, terminal_role, description",
    )
    expected_tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        doc="Expected tool invocations and argument matching rules",
    )
    ordering_constraints: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Execution sequence rules: STRICT_SEQUENCE, DEPENDENCY_DAG, or UNORDERED",
    )
    forbidden_tool_calls: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        doc="Array of tool names that must NOT be called",
    )
    reference_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Reference facts for hallucination detection: required_facts, forbidden_facts",
    )
    deterministic_assertions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        doc="Deterministic rule assertions: turn limits, latency budgets, schema checks",
    )
    qualitative_criteria: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        doc="Qualitative LLM-as-a-Judge criteria: groundedness, politeness, policy alignment",
    )
    mock_environment_fixtures: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Synthetic mock tool responses scoped exclusively to this scenario",
    )
    max_turns: Mapped[int] = mapped_column(
        Integer,
        default=8,
        nullable=False,
        doc="Maximum turn ceiling before terminating execution",
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=45,
        nullable=False,
        doc="Per-execution timeout budget in seconds",
    )

    # Relationships
    test_suite: Mapped["TestSuite"] = relationship(back_populates="test_cases")
    executions: Mapped[list["TestExecution"]] = relationship(
        back_populates="test_case",
    )
