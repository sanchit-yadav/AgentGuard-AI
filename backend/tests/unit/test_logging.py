"""Unit tests for structured JSON logging and sensitive data sanitization."""

import json
import logging
from io import StringIO

from app.core.logging import (
    JSONFormatter,
    SensitiveDataFilter,
    sanitize_message,
    setup_logging,
)


def test_sanitize_message_scrubs_bearer_tokens() -> None:
    """Verify that Bearer tokens are scrubbed from message text."""
    raw = "Connecting with header Authorization: Bearer sk-1234567890abcdef12345"
    sanitized = sanitize_message(raw)

    assert "sk-1234567890abcdef12345" not in sanitized
    assert "Bearer [REDACTED]" in sanitized


def test_sanitize_message_scrubs_api_keys() -> None:
    """Verify that API keys are scrubbed from message text."""
    raw = "Failed request with api_key: sk-proj-abcdef1234567890abcdef"
    sanitized = sanitize_message(raw)

    assert "sk-proj-abcdef1234567890abcdef" not in sanitized
    assert "[REDACTED]" in sanitized


def test_sanitize_message_scrubs_passwords() -> None:
    """Verify that password parameters are scrubbed from message text."""
    raw = "Connection string postgresql://user:mysecretpassword123@localhost/db"
    sanitized = sanitize_message(raw)

    assert "mysecretpassword123" not in sanitized
    assert "[REDACTED]" in sanitized


def test_json_formatter_outputs_valid_json() -> None:
    """Verify that JSONFormatter produces valid JSON with required schema fields."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="Test event message occurred",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test event message occurred"
    assert "timestamp" in parsed


def test_json_formatter_includes_exception_trace() -> None:
    """Verify that exception stack traces are captured in JSON output."""
    formatter = JSONFormatter()

    try:
        raise ValueError("Simulated operational failure")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname=__file__,
        lineno=65,
        msg="Operation failed",
        args=(),
        exc_info=exc_info,
    )

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "ERROR"
    assert "exception" in parsed
    assert "ValueError: Simulated operational failure" in parsed["exception"]


def test_logging_pipeline_sanitizes_live_log_records() -> None:
    """Verify that log records dispatched through the configured handler scrub secrets."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())

    test_logger = logging.getLogger("test_pipeline_logger")
    test_logger.handlers.clear()
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)

    test_logger.info("Agent dispatched request with Bearer secret-agent-token-987654321")

    output = stream.getvalue().strip()
    parsed = json.loads(output)

    assert "secret-agent-token-987654321" not in parsed["message"]
    assert "Bearer [REDACTED]" in parsed["message"]


def test_setup_logging_initialization() -> None:
    """Verify that setup_logging configures root logger without exceptions."""
    setup_logging(log_level="DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) >= 1
