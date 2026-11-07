"""OpenTelemetry-compatible ExecutionTrace and chronological ExecutionEvent models."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.test_run import TestExecution


class ExecutionTrace(Base, UUIDPrimaryKeyMixin):
    """OpenTelemetry-compatible trace header linking all discrete events for an execution."""

    __tablename__ = "execution_traces"

    test_execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_executions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        doc="One-to-one foreign key reference to parent test execution",
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        nullable=False,
        index=True,
        doc="W3C-compatible trace identifier linking spans across distributed services",
    )
    turn_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Total number of conversational turns completed in this trace",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp when execution trace began",
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when execution trace ended",
    )

    # Relationships
    test_execution: Mapped["TestExecution"] = relationship(back_populates="trace")
    events: Mapped[list["ExecutionEvent"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExecutionEvent.event_index",
    )


class ExecutionEvent(Base, UUIDPrimaryKeyMixin):
    """Append-only chronological record of an observable event occurring during agent execution."""

    __tablename__ = "execution_events"
    __table_args__ = (
        Index("ix_execution_events_trace_idx", "execution_trace_id", "event_index"),
        Index("ix_execution_events_type", "event_type"),
        Index("ix_execution_events_payload", "payload", postgresql_using="gin"),
    )

    execution_trace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_traces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent execution trace",
    )
    event_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="0-indexed order of event within trace to ensure deterministic sorting",
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Category: USER_PROMPT, AGENT_RAW_RESPONSE, TOOL_CALL_INVOKED, MOCK_TOOL_RESULT, AGENT_ERROR, EVALUATOR_VERDICT",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        doc="Structured event payload (tool name, serialized arguments, token counts, error message)",
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Discrete duration of this event in milliseconds",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
        doc="Accurate UTC timestamp when the event occurred",
    )

    # Relationships
    trace: Mapped["ExecutionTrace"] = relationship(back_populates="events")
