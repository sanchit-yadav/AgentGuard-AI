"""Target AI agent, encrypted credentials, version snapshots, and tool models."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.test_run import TestRun


class Agent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Registered target AI agent under test."""

    __tablename__ = "agents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent project workspace",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable agent display name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Agent business domain description and operational purpose",
    )
    endpoint_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        doc="Target HTTP API endpoint URL (OpenAI-compatible / turn-based)",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="HEALTHY",
        nullable=False,
        doc="Operational health status: HEALTHY, UNREACHABLE, or DISABLED",
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="agents")
    credentials: Mapped["AgentCredential | None"] = relationship(
        back_populates="agent",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tools: Mapped[list["AgentTool"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AgentCredential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Encrypted authentication credentials for accessing target agent endpoints."""

    __tablename__ = "agent_credentials"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        doc="One-to-one foreign key reference to target agent",
    )
    auth_type: Mapped[str] = mapped_column(
        String(50),
        default="BEARER_TOKEN",
        nullable=False,
        doc="Authentication protocol: BEARER_TOKEN, API_KEY_HEADER, CUSTOM_HEADERS, NONE",
    )
    encrypted_payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="AES-256-GCM ciphertext containing token or header secrets",
    )
    key_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Identifier for the KMS key or master key used for encryption",
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(back_populates="credentials")


class AgentVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable point-in-time snapshot of an agent configuration.

    Guarantees that historical test runs are reproducible against the exact
    prompts, tool schemas, and model settings originally tested.
    """

    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version_tag", name="uq_agent_versions_agent_tag"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent agent",
    )
    version_tag: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="SemVer version tag or revision identifier (e.g., v1.0.0, v1.1.0-fix)",
    )
    system_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Frozen system instructions active during this version",
    )
    model_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Frozen model configuration: provider, model snapshot ID, temperature, seed",
    )
    endpoint_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        doc="Target HTTP API endpoint URL active during this version",
    )
    tools_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        doc="Frozen array of all registered tool schemas [{name, description, parameters_schema}]",
    )
    auth_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Snapshot of authentication protocol metadata",
    )
    evaluation_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Snapshot of evaluation thresholds, turn limits, and timeouts",
    )
    is_immutable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Locked to True after initial test run execution; prevents further mutation",
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(back_populates="versions")
    test_runs: Mapped[list["TestRun"]] = relationship(back_populates="agent_version")


class AgentTool(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Working catalog/drafting space of tools configured for an agent."""

    __tablename__ = "agent_tools"
    __table_args__ = (
        UniqueConstraint("agent_id", "name", name="uq_agent_tools_agent_name"),
        Index("ix_agent_tools_schema", "parameters_schema", postgresql_using="gin"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent agent",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Tool function name (e.g., get_order_details, create_refund)",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Description provided to the agent model explaining tool purpose",
    )
    parameters_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        doc="JSON Schema defining required and optional tool arguments",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether this tool is currently exposed to the agent during execution",
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(back_populates="tools")
