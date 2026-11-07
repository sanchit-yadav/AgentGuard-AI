"""Unit tests for domain models verifying tables, constraints, relationships, and mixins."""

import uuid
from typing import cast

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import (
    Agent,
    AgentCredential,
    AgentTool,
    AgentVersion,
    Base,
    Evaluation,
    EvaluationMetric,
    ExecutionEvent,
    ExecutionTrace,
    Organization,
    OrganizationMember,
    Project,
    RegressionResult,
    Report,
    SecurityFinding,
    TestCase,
    TestExecution,
    TestRun,
    TestSuite,
    User,
)


def table_of(model: type[Base]) -> Table:
    """Return typed Table object from declarative model class."""
    return cast(Table, model.__table__)


def test_all_models_registered_in_metadata() -> None:
    """Verify that all 15 core domain models are registered in Base.metadata with expected tables."""
    expected_tables = {
        "organizations",
        "users",
        "organization_members",
        "projects",
        "agents",
        "agent_credentials",
        "agent_versions",
        "agent_tools",
        "test_suites",
        "test_cases",
        "test_runs",
        "test_executions",
        "execution_traces",
        "execution_events",
        "evaluations",
        "evaluation_metrics",
        "security_findings",
        "regression_results",
        "reports",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables)


def test_organization_and_user_models() -> None:
    """Verify Organization, User, and OrganizationMember model configurations."""
    # Organization
    org_table = table_of(Organization)
    assert org_table.name == "organizations"
    assert org_table.c.id.primary_key is True
    assert org_table.c.slug.unique is True
    assert org_table.c.name.nullable is False

    # User
    user_table = table_of(User)
    assert user_table.name == "users"
    assert user_table.c.email.unique is True
    assert user_table.c.is_active.nullable is False
    assert user_table.c.is_verified.nullable is False
    assert getattr(user_table.c.is_active.default, "arg", None) is True
    assert getattr(user_table.c.is_verified.default, "arg", None) is False

    # Member
    member_table = table_of(OrganizationMember)
    assert member_table.name == "organization_members"
    assert any(
        uq.name == "uq_organization_members_org_user"
        for uq in member_table.constraints
        if hasattr(uq, "columns") and len(uq.columns) == 2
    )

    # Instantiation checks
    org = Organization(name="Acme Corp", slug="acme-corp")
    assert org.name == "Acme Corp"
    assert org.slug == "acme-corp"

    user = User(
        email="dev@acme.com",
        hashed_password="secure_hash",
        full_name="Staff Engineer",
        is_active=True,
        is_verified=False,
    )
    assert user.email == "dev@acme.com"
    assert user.is_active is True
    assert user.is_verified is False


def test_project_model() -> None:
    """Verify Project model constraints and organization scoping."""
    proj_table = table_of(Project)
    assert proj_table.name == "projects"
    assert any(
        uq.name == "uq_projects_org_slug"
        for uq in proj_table.constraints
        if hasattr(uq, "columns") and len(uq.columns) == 2
    )
    # Check FK to organizations
    fk = list(proj_table.c.organization_id.foreign_keys)[0]
    assert fk.column.table.name == "organizations"
    assert fk.ondelete == "CASCADE"

    # Instantiation
    proj = Project(
        organization_id=uuid.uuid4(),
        name="Support Bot Testing",
        slug="support-bot-testing",
        description="Testing suite for customer support assistant",
    )
    assert proj.name == "Support Bot Testing"


def test_agent_models() -> None:
    """Verify Agent, AgentCredential, AgentVersion, and AgentTool configurations."""
    # Agent
    agent_table = table_of(Agent)
    assert agent_table.name == "agents"
    assert agent_table.c.endpoint_url.nullable is False

    # AgentCredential
    cred_table = table_of(AgentCredential)
    assert cred_table.name == "agent_credentials"
    assert cred_table.c.agent_id.unique is True

    # AgentVersion
    ver_table = table_of(AgentVersion)
    assert ver_table.name == "agent_versions"
    assert isinstance(ver_table.c.model_config.type, JSONB)
    assert isinstance(ver_table.c.tools_snapshot.type, JSONB)
    assert isinstance(ver_table.c.evaluation_config.type, JSONB)
    assert any(
        uq.name == "uq_agent_versions_agent_tag"
        for uq in ver_table.constraints
        if hasattr(uq, "columns") and len(uq.columns) == 2
    )

    # AgentTool
    tool_table = table_of(AgentTool)
    assert tool_table.name == "agent_tools"
    assert isinstance(tool_table.c.parameters_schema.type, JSONB)
    assert any(
        uq.name == "uq_agent_tools_agent_name"
        for uq in tool_table.constraints
        if hasattr(uq, "columns") and len(uq.columns) == 2
    )
    # Check GIN index
    gin_indices = [
        idx
        for idx in tool_table.indexes
        if getattr(idx, "dialect_options", {}).get("postgresql", {}).get("using")
        == "gin"
    ]
    assert len(gin_indices) == 1
    assert "parameters_schema" in [c.name for c in gin_indices[0].columns]


def test_test_suite_and_case_models() -> None:
    """Verify TestSuite and TestCase rich scenario JSONB fields and constraints."""
    suite_table = table_of(TestSuite)
    assert suite_table.name == "test_suites"

    case_table = table_of(TestCase)
    assert case_table.name == "test_cases"
    # Verify rich structured scenario JSONB columns
    jsonb_cols = [
        "conversation_turns",
        "expected_outcome",
        "expected_tool_calls",
        "ordering_constraints",
        "forbidden_tool_calls",
        "reference_data",
        "deterministic_assertions",
        "qualitative_criteria",
        "mock_environment_fixtures",
    ]
    for col_name in jsonb_cols:
        col = case_table.c[col_name]
        assert isinstance(col.type, JSONB), f"Expected column {col_name} to be JSONB"

    assert getattr(case_table.c.max_turns.default, "arg", None) == 8
    assert getattr(case_table.c.timeout_seconds.default, "arg", None) == 45

    # Instantiation
    case = TestCase(
        test_suite_id=uuid.uuid4(),
        title="Refund Policy Limit Test",
        test_type="FUNCTIONAL",
        conversation_turns=[{"role": "user", "content": "I want a refund for $500"}],
        expected_outcome={"status": "escalated"},
        expected_tool_calls=[{"tool_name": "escalate_to_human"}],
        ordering_constraints=[],
        forbidden_tool_calls=["issue_direct_refund"],
        reference_data={"max_automated_refund": 100},
        deterministic_assertions=[
            {"assertion_type": "status_equals", "value": "escalated"}
        ],
        qualitative_criteria={"empathy": 0.8},
        mock_environment_fixtures={},
        max_turns=8,
        timeout_seconds=45,
    )
    assert case.title == "Refund Policy Limit Test"
    assert case.max_turns == 8
    assert case.timeout_seconds == 45


def test_test_run_and_execution_models() -> None:
    """Verify TestRun and TestExecution models with cascades and RESTRICT constraints."""
    run_table = table_of(TestRun)
    assert run_table.name == "test_runs"

    # agent_version_id has RESTRICT ondelete to prevent deleting versions associated with test runs
    agent_ver_fk = list(run_table.c.agent_version_id.foreign_keys)[0]
    assert agent_ver_fk.ondelete == "RESTRICT"

    exec_table = table_of(TestExecution)
    assert exec_table.name == "test_executions"
    # test_case_id has RESTRICT ondelete
    case_fk = list(exec_table.c.test_case_id.foreign_keys)[0]
    assert case_fk.ondelete == "RESTRICT"

    # Verify partial index on failure_category
    partial_indices = [
        idx for idx in exec_table.indexes if idx.name == "ix_test_executions_failure"
    ]
    assert len(partial_indices) == 1


def test_trace_and_event_models() -> None:
    """Verify ExecutionTrace and ExecutionEvent models, OTel compliance, and GIN indexing."""
    trace_table = table_of(ExecutionTrace)
    assert trace_table.name == "execution_traces"
    assert trace_table.c.test_execution_id.unique is True
    assert trace_table.c.trace_id.unique is True
    assert isinstance(trace_table.c.trace_id.type, UUID)

    event_table = table_of(ExecutionEvent)
    assert event_table.name == "execution_events"
    assert isinstance(event_table.c.payload.type, JSONB)

    # Check GIN index on event payload
    gin_indices = [
        idx
        for idx in event_table.indexes
        if getattr(idx, "dialect_options", {}).get("postgresql", {}).get("using")
        == "gin"
    ]
    assert len(gin_indices) == 1
    assert "payload" in [c.name for c in gin_indices[0].columns]


def test_evaluation_sub_models() -> None:
    """Verify Evaluation, Metric, SecurityFinding, RegressionResult, and Report models."""
    eval_table = table_of(Evaluation)
    assert eval_table.name == "evaluations"
    assert isinstance(eval_table.c.generation_parameters.type, JSONB)
    assert isinstance(eval_table.c.structured_evidence.type, JSONB)
    assert isinstance(eval_table.c.token_usage.type, JSONB)

    metric_table = table_of(EvaluationMetric)
    assert metric_table.name == "evaluation_metrics"
    metric_fk = list(metric_table.c.evaluation_id.foreign_keys)[0]
    assert metric_fk.column.table.name == "evaluations"

    sec_table = table_of(SecurityFinding)
    assert sec_table.name == "security_findings"
    assert isinstance(sec_table.c.raw_evidence.type, JSONB)

    reg_table = table_of(RegressionResult)
    assert reg_table.name == "regression_results"
    base_fk = list(reg_table.c.base_run_id.foreign_keys)[0]
    assert base_fk.column.table.name == "test_runs"

    rep_table = table_of(Report)
    assert rep_table.name == "reports"
    assert rep_table.c.report_format.nullable is False
