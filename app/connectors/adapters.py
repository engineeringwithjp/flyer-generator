"""Concrete connector adapters.

Each adapter is a thin, dependency-free shim. It reports `NOT_INSTALLED` unless
a credential or a host-provided client is actually present, so the repository
stays runnable with none of these configured.

**Honest status at the time of writing:** none of these four services has been
called from this repository. The adapters, the decision engine, the provenance
model and the fallbacks are implemented and tested; the live calls are not,
because the connectors require authorisation that has not been completed.
Wiring one up means implementing its ``_search`` and nothing else.
"""

from __future__ import annotations

import os

from ..logging_setup import get_logger
from .base import BaseConnector, ConnectorResult, ConnectorRole, ConnectorStatus

log = get_logger(__name__)


class UnsplashConnector(BaseConnector):
    """Supplemental photography. Fills gaps in the internal library only."""

    name = "unsplash"
    role = ConnectorRole.ASSET

    def _probe(self) -> ConnectorStatus:
        if not os.getenv("UNSPLASH_ACCESS_KEY"):
            return ConnectorStatus.CONFIGURATION_REQUIRED
        return ConnectorStatus.AVAILABLE

    def _search(self, query: str, limit: int, **kwargs) -> ConnectorResult:
        """Unsplash Search Photos API.

        Returns items shaped for ``app.assets`` with full provenance. Only
        reached when ``UNSPLASH_ACCESS_KEY`` is set.
        """
        import json
        import urllib.parse
        import urllib.request

        url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(
            {
                "query": query,
                "per_page": min(limit, 10),
                "orientation": "landscape",
                "content_filter": "high",
            }
        )
        request = urllib.request.Request(
            url, headers={"Authorization": f"Client-ID {os.environ['UNSPLASH_ACCESS_KEY']}"}
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read())

        items = [
            {
                "download_url": photo["urls"]["raw"] + "&w=2000&q=85",
                "width": photo.get("width", 0),
                "height": photo.get("height", 0),
                "description": photo.get("alt_description") or photo.get("description") or "",
                "source": {
                    "source": "unsplash",
                    "source_id": photo["id"],
                    "source_url": photo["links"]["html"],
                    "author": (photo.get("user") or {}).get("name", ""),
                    "licence": "Unsplash License",
                    "usage_context": "background photography",
                },
            }
            for photo in payload.get("results", [])
        ]
        return ConnectorResult(status=ConnectorStatus.AVAILABLE, items=items)


class MobbinConnector(BaseConnector):
    """Visual-pattern research. Reference only - never flyer artwork."""

    name = "mobbin"
    role = ConnectorRole.REFERENCE

    def _probe(self) -> ConnectorStatus:
        # Mobbin has no public API. It reaches this repository through an
        # authorised host connector, which is not present in this environment.
        return ConnectorStatus.NOT_INSTALLED


class FigmaConnector(BaseConnector):
    """Master design system and editable source files."""

    name = "figma"
    role = ConnectorRole.TEMPLATE

    def _probe(self) -> ConnectorStatus:
        if not os.getenv("FIGMA_ACCESS_TOKEN"):
            return ConnectorStatus.CONFIGURATION_REQUIRED
        return ConnectorStatus.AVAILABLE

    def _search(self, query: str, limit: int, **kwargs) -> ConnectorResult:
        import json
        import urllib.request

        file_key = kwargs.get("file_key") or os.getenv("FIGMA_FILE_KEY")
        if not file_key:
            return ConnectorResult(
                status=ConnectorStatus.CONFIGURATION_REQUIRED,
                message="Set FIGMA_FILE_KEY to the master flyer-system file.",
            )
        request = urllib.request.Request(
            f"https://api.figma.com/v1/files/{file_key}",
            headers={"X-Figma-Token": os.environ["FIGMA_ACCESS_TOKEN"]},
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read())

        frames = [
            {
                "name": node.get("name", ""),
                "node_id": node.get("id", ""),
                "source": {
                    "source": "figma",
                    "source_id": node.get("id", ""),
                    "source_url": f"https://figma.com/file/{file_key}?node-id={node.get('id', '')}",
                    "usage_context": "master layout",
                },
            }
            for page in payload.get("document", {}).get("children", [])
            for node in page.get("children", [])
            if node.get("type") == "FRAME"
        ][:limit]
        return ConnectorResult(status=ConnectorStatus.AVAILABLE, items=frames)


class CanvaConnector(BaseConnector):
    """Client-editable deliverables."""

    name = "canva"
    role = ConnectorRole.PRODUCTION

    def _probe(self) -> ConnectorStatus:
        if not os.getenv("CANVA_ACCESS_TOKEN"):
            return ConnectorStatus.CONFIGURATION_REQUIRED
        return ConnectorStatus.AVAILABLE


ADAPTERS: dict[str, type[BaseConnector]] = {
    "unsplash": UnsplashConnector,
    "mobbin": MobbinConnector,
    "figma": FigmaConnector,
    "canva": CanvaConnector,
}
