"""Structured application logging for AgentGuard AI.

Provides JSON-formatted logs with timestamps, log levels, logger names,
exception stack traces, and automatic sanitization of sensitive data
(passwords, tokens, API keys, credentials).
"""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Regular expressions for detecting and scrubbing sensitive data
SENSITIVE_PATTERNS = [
    re.compile(r"(bearer\s+)[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key[\"']?\s*[:=]\s*[\"']?)[a-zA-Z0-9_\-\.]{16,}([\"']?)", re.IGNORECASE),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"']?)[^\"'\s,]{6,}([\"']?)", re.IGNORECASE),
    re.compile(r"(secret[_-]?key[\"']?\s*[:=]\s*[\"']?)[^\"'\s,]{16,}([\"']?)", re.IGNORECASE),
    re.compile(r"(token[\"']?\s*[:=]\s*[\"']?)[a-zA-Z0-9_\-\.]{16,}([\"']?)", re.IGNORECASE),
    re.compile(r"(://[^:\s@]+:)[^@\s/]+(@)", re.IGNORECASE),
]


def sanitize_message(message: str) -> str:
    """Scrub sensitive tokens, passwords, and API keys from a log message string."""
    sanitized = message
    for pattern in SENSITIVE_PATTERNS:
        if "bearer" in pattern.pattern:
            sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
        elif "://" in pattern.pattern:
            sanitized = pattern.sub(r"\1[REDACTED]\2", sanitized)
        else:
            sanitized = pattern.sub(r"\1[REDACTED]\2", sanitized)
    return sanitized


class SensitiveDataFilter(logging.Filter):
    """Logging filter that scrubs sensitive patterns from all record messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_message(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: sanitize_message(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_message(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True


class JSONFormatter(logging.Formatter):
    """Formats log records as structured, single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        # ISO-8601 UTC timestamp
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()

        log_payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include location in non-INFO/DEBUG logs or when debug enabled
        if record.levelno >= logging.WARNING:
            log_payload["caller"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Include exception traceback if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            log_payload["exception"] = record.exc_text

        # Include custom extra fields if attached to record
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message",
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in standard_attrs}
        if extras:
            log_payload["extra"] = extras

        return json.dumps(log_payload, default=str)


def setup_logging(log_level: str = "INFO") -> None:
    """Initialize structured application logging with sanitization filters.

    Args:
        log_level: Minimum log level string ("DEBUG", "INFO", "WARNING", "ERROR").
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure root logger handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers to prevent duplicate lines
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Silence excessively verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a scoped logger instance with the sensitive data filter attached."""
    logger = logging.getLogger(name)
    return logger
