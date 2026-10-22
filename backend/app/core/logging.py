"""EdgeErgo V3 — Structured JSON Logging & Secret Redaction Filter."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

# Regex patterns for sensitive tokens and connection strings
REDACTION_PATTERNS = [
    # Bearer / JWT tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]+", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+"), "[JWT_REDACTED]"),
    # Device credentials & tokens
    (re.compile(r"eed_[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "eed_[REDACTED]"),
    (re.compile(r"eet_[A-Za-z0-9_\-]+"), "eet_[REDACTED]"),
    # Database connection passwords
    (
        re.compile(r"(postgres(?:ql)?(?:\+[a-z0-9]+)?://[^:]+:)[^@]+(@)", re.IGNORECASE),
        r"\1[REDACTED]\2",
    ),
    # Generic password / secret assignments
    (
        re.compile(r'("(?:password|secret|token|credential|api_key)":\s*")[^"]+(")', re.IGNORECASE),
        r"\1[REDACTED]\2",
    ),
]


def redact_sensitive_text(text: str) -> str:
    """Applies regex redaction to strip tokens, passwords, and secrets from log strings."""
    redacted = text
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class RedactingJsonFormatter(logging.Formatter):
    """Outputs structured JSON log records with automated secret scrubbing."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(record.getMessage()),
        }

        # Include request ID if present in log record
        if hasattr(record, "request_id"):
            log_payload["request_id"] = record.request_id

        if record.exc_info and record.exc_text:
            log_payload["exception"] = redact_sensitive_text(record.exc_text)

        return json.dumps(log_payload, default=str)


def setup_logging(log_level: str = "INFO") -> None:
    """Configures root logger with RedactingJsonFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers to avoid duplicate un-redacted logs
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(RedactingJsonFormatter())
    root_logger.addHandler(console_handler)
