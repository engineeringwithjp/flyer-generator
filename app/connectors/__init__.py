"""External design and content connectors.

Supplemental by construction: the pipeline completes with every one of them
unavailable. ``policy.decide`` chooses which, if any, earn their place, and
records the reasoning in the generation history.
"""

from .base import (
    BaseConnector,
    Connector,
    ConnectorResult,
    ConnectorRole,
    ConnectorStatus,
    SourceRef,
)
from .policy import ConnectorOverrides, ToolDecision, decide, parse_overrides
from .registry import all_connectors, available_names, clear_cache, get, status_report

__all__ = [
    "BaseConnector",
    "Connector",
    "ConnectorOverrides",
    "ConnectorResult",
    "ConnectorRole",
    "ConnectorStatus",
    "SourceRef",
    "ToolDecision",
    "available_names",
    "clear_cache",
    "decide",
    "get",
    "parse_overrides",
    "all_connectors",
    "status_report",
]
