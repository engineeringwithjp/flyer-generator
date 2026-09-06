"""Structured logging with secret redaction.

Every log line is prefixed with the active generation run id when one is set,
so a GitHub Actions log can be read top-to-bottom for a single run.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from contextvars import ContextVar

_run_id: ContextVar[str] = ContextVar("run_id", default="-")

# Anything that looks like a credential is masked before it reaches a log sink.
_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"ya29\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"1//[A-Za-z0-9_\-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
]


def set_run_id(run_id: str) -> None:
    _run_id.set(run_id)


def get_run_id() -> str:
    return _run_id.get()


def redact(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class _RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.run_id = _run_id.get()
        return redact(super().format(record))


def configure_logging(level: str | None = None) -> None:
    """Idempotent root-logger setup."""
    resolved = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    root = logging.getLogger()
    root.setLevel(resolved)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _RedactingFormatter("%(asctime)s  %(levelname)-7s  [%(run_id)s]  %(name)s: %(message)s")
    )
    root.addHandler(handler)
    # These libraries are extremely chatty at INFO.
    for noisy in ("httpx", "httpcore", "anthropic", "googleapiclient.discovery_cache", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
