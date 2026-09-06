"""Shared fixtures.

Every test runs against a temporary repository root so nothing touches the real
libraries, indexes or history. No test may make a network call.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

REAL_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Hard-fail any accidental outbound HTTP in a unit test."""
    import socket

    def guard(*args, **kwargs):  # pragma: no cover - only runs on a violation
        raise RuntimeError(
            "A unit test attempted a network connection. Mock the external service, "
            "or mark the test with @pytest.mark.integration."
        )

    monkeypatch.setattr(socket.socket, "connect", guard)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A minimal but complete repository root in a temp directory."""
    root = tmp_path / "repo"
    for folder in (
        "config",
        "clients/testco/assets/logo",
        "clients/testco/assets/approved",
        "assets/roofing",
        "assets/siding",
        "assets/general",
        "assets/fonts",
        "references/inbox",
        "references/approved",
        "references/experimental",
        "references/rejected",
        "data/references",
        "data/assets",
        "data/generation-history",
        "design-system/principles",
        "design-system/preferences",
        "design-system/patterns",
        "design-system/failures",
        "design-system/historical-prompts/successful",
        "design-system/historical-prompts/unsuccessful",
        "output",
        ".claude/skills/construction-flyer",
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)

    # Real config and skill content - these are part of what we are testing.
    for name in (
        "campaigns.json",
        "scoring.json",
        "layouts.json",
        "typography.json",
        "connectors.json",
        "stage-policy.json",
    ):
        shutil.copy2(REAL_ROOT / "config" / name, root / "config" / name)
    for path in (REAL_ROOT / ".claude/skills/construction-flyer").glob("*.md"):
        shutil.copy2(path, root / ".claude/skills/construction-flyer" / path.name)
    for sub, name in (
        ("principles", "principles.json"),
        ("preferences", "preferences.json"),
        ("patterns", "successful-patterns.json"),
        ("failures", "failed-patterns.json"),
    ):
        shutil.copy2(REAL_ROOT / "design-system" / sub / name, root / "design-system" / sub / name)

    # Real fonts if they have been fetched; the renderer falls back if not.
    real_fonts = REAL_ROOT / "assets" / "fonts"
    if real_fonts.exists():
        for font in real_fonts.glob("*.ttf"):
            shutil.copy2(font, root / "assets" / "fonts" / font.name)

    (root / "clients/testco/client.json").write_text(
        json.dumps(
            {
                "id": "testco",
                "company_name": "Testco Roofing LLC",
                "location": "New Jersey",
                "service_area": ["Bergen County"],
                "services": ["Roofing", "Siding"],
                "tone": ["professional", "trustworthy"],
                "primary_goal": "lead_generation",
                "brand": {
                    "primary_colors": ["#12243A"],
                    "secondary_colors": ["#E0A62F"],
                    "neutral_colors": ["#FFFFFF", "#111111"],
                    "logo_path": "assets/logo/logo.png",
                },
                "contact": {
                    "phone": "(201) 555-0142",
                    "website": "testco.example",
                    "email": "hello@testco.example",
                },
                "offers": [
                    {
                        "id": "fall-inspection",
                        "text": "Free Roof Inspection",
                        "fine_print": "Residential only.",
                        "services": ["roofing"],
                    }
                ],
                "products": [
                    {
                        "id": "test-shingle",
                        "name": "TestBrand Architectural Shingle",
                        "manufacturer": "TestBrand",
                        "category": "roofing",
                        "benefits": ["Architectural profile"],
                    }
                ],
                "proof_points": [
                    "Licensed & insured New Jersey contractor",
                    "NJ HIC #13VH00000000",
                ],
                "enabled": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _write_image(root / "assets/roofing/roof-one.jpg", (90, 100, 112))
    _write_image(root / "assets/roofing/roof-two.jpg", (150, 158, 168))
    _write_image(root / "assets/siding/siding-one.jpg", (170, 180, 190))
    _write_image(root / "clients/testco/assets/approved/roofing-client-shot.jpg", (70, 80, 92))
    _write_image(root / "clients/testco/assets/logo/logo.png", (255, 255, 255), size=(400, 120))

    monkeypatch.setenv("FLYER_ROOT", str(root))
    monkeypatch.setenv("FLYER_OFFLINE", "1")
    monkeypatch.setenv("DEFAULT_CLIENT", "testco")
    for secret in (
        "ANTHROPIC_API_KEY",
        "GOOGLE_DRIVE_ROOT_FOLDER_ID",
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_SERVICE_ACCOUNT_FILE",
    ):
        monkeypatch.delenv(secret, raising=False)

    _reset_caches()
    yield root
    _reset_caches()


def _reset_caches() -> None:
    """Every module-level cache that depends on the repository root."""
    import app.design_system as design_system
    from app.ai import skill
    from app.config import reset_settings_cache
    from app.connectors import clear_cache as clear_connector_cache

    reset_settings_cache()
    design_system.clear_cache()
    skill.clear_cache()
    clear_connector_cache()


def _write_image(path: Path, color, size=(1600, 1200)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color)
    # A little structure so contrast/variance analysis has something to read.
    for x in range(0, size[0], 90):
        for y in range(0, size[1], 90):
            image.paste(
                tuple(min(255, c + 26) for c in color),
                (x, y, min(x + 45, size[0]), min(y + 45, size[1])),
            )
    image.save(path, quality=90)


@pytest.fixture()
def client(repo):
    from app.clients.loader import load_client

    return load_client("testco")


@pytest.fixture()
def settings(repo):
    from app.config import get_settings

    return get_settings()
