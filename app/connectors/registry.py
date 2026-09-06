"""Connector registry and status reporting."""

from __future__ import annotations

from functools import lru_cache

from ..config import load_json_config
from ..logging_setup import get_logger
from .adapters import ADAPTERS
from .base import BaseConnector, ConnectorStatus

log = get_logger(__name__)


def config() -> dict:
    return load_json_config("connectors.json")


@lru_cache(maxsize=1)
def all_connectors() -> dict[str, BaseConnector]:
    """Every registered connector, built once per process."""
    settings = config().get("connectors", {})
    return {name: adapter(settings.get(name, {})) for name, adapter in ADAPTERS.items()}


def clear_cache() -> None:
    # Tolerant of a monkeypatched stand-in during tests.
    clear = getattr(all_connectors, "cache_clear", None)
    if callable(clear):
        clear()


def get(name: str) -> BaseConnector | None:
    return all_connectors().get(name)


def status_report() -> dict[str, dict]:
    """What is actually reachable right now. Used by `flyer connectors`."""
    settings = config().get("connectors", {})
    report: dict[str, dict] = {}
    for name, connector in all_connectors().items():
        status = connector.probe()
        report[name] = {
            "status": status.value,
            "role": connector.role.value,
            "description": settings.get(name, {}).get("description", ""),
            "use_when": settings.get(name, {}).get("use_when", ""),
            "fallback": _fallback_for(connector.role.value),
        }
    return report


def _fallback_for(role: str) -> str:
    return {
        "asset": "approved internal backgrounds, then a procedural brand background",
        "reference": "the internal reference library, then the design system defaults",
        "template": "the local design system and the internal renderer",
        "production": "the internal renderer (a PNG rather than an editable file)",
    }.get(role, "internal defaults")


def available_names() -> list[str]:
    return [
        name
        for name, connector in all_connectors().items()
        if connector.probe() is ConnectorStatus.AVAILABLE
    ]
