"""Connector contract.

Every external design or content service implements this interface. The rules
that make the whole thing safe:

* A connector is **supplemental**. The pipeline must complete with all of them
  unavailable.
* A connector never decides that it should be used. ``app.connectors.policy``
  decides, and records why.
* Anything a connector returns carries provenance and is cached, so the same
  source is never fetched twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ConnectorRole(StrEnum):
    ASSET = "asset"  # supplies imagery that goes INTO the flyer
    REFERENCE = "reference"  # supplies design DNA to learn FROM
    TEMPLATE = "template"  # supplies editable layout systems
    PRODUCTION = "production"  # produces an editable client deliverable


class ConnectorStatus(StrEnum):
    AVAILABLE = "available"  # verified reachable this session
    CONFIGURATION_REQUIRED = "config_required"  # present but not authorised
    NOT_INSTALLED = "not_installed"  # no adapter reachable here
    DISABLED = "disabled"  # switched off in config
    FAILED = "failed"  # tried and errored


class SourceRef(BaseModel):
    """Provenance for anything that came from outside the repository.

    Never fabricated, never stripped once recorded.
    """

    source: str = Field(description="internal | unsplash | mobbin | figma | canva")
    source_id: str = ""
    source_url: str = ""
    author: str = ""
    licence: str = ""
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    usage_context: str = Field(default="", description="e.g. 'background photography'")

    @property
    def is_internal(self) -> bool:
        return self.source in ("", "internal", "client")


@dataclass
class ConnectorResult:
    """What a connector returns. Empty is a normal, non-fatal outcome."""

    status: ConnectorStatus
    items: list[dict] = field(default_factory=list)
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status is ConnectorStatus.AVAILABLE and bool(self.items)


@runtime_checkable
class Connector(Protocol):
    name: str
    role: ConnectorRole

    def probe(self) -> ConnectorStatus:
        """Cheap availability check. Must never raise."""

    def search(self, query: str, limit: int = 5, **kwargs) -> ConnectorResult:
        """Return candidate items with provenance. Must never raise."""


class BaseConnector:
    """Shared behaviour: never raise, always report a status."""

    name: str = "base"
    role: ConnectorRole = ConnectorRole.REFERENCE

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", True))

    def probe(self) -> ConnectorStatus:
        if not self.enabled:
            return ConnectorStatus.DISABLED
        return self._probe()

    def _probe(self) -> ConnectorStatus:  # pragma: no cover - overridden
        return ConnectorStatus.NOT_INSTALLED

    def search(self, query: str, limit: int = 5, **kwargs) -> ConnectorResult:
        status = self.probe()
        if status is not ConnectorStatus.AVAILABLE:
            return ConnectorResult(
                status=status,
                message=f"{self.name} is {status.value}; the internal library is being used instead.",
            )
        try:
            return self._search(query, limit, **kwargs)
        except Exception as exc:  # a connector must never break a run
            return ConnectorResult(
                status=ConnectorStatus.FAILED,
                message=f"{self.name} failed: {exc}. Falling back to internal sources.",
            )

    def _search(self, query: str, limit: int, **kwargs) -> ConnectorResult:  # pragma: no cover
        return ConnectorResult(status=ConnectorStatus.NOT_INSTALLED)
