"""Work-state policy.

The bug this prevents: a flyer selling premium roofing showing a worn-out or
half-stripped roof. Confusing at best, dishonest at worst.
"""

from __future__ import annotations

import pytest
from PIL import Image

from app.assets.catalog import AssetCatalog
from app.assets.metadata import infer_stage
from app.assets.selector import allowed_stages, select_asset, stage_permitted
from app.models import ApprovalStatus, Asset, Provenance, SourceType


def _asset(stage: str, name: str = "x") -> Asset:
    return Asset(
        id=name,
        path=f"clients/testco/assets/approved/{name}.jpg",
        service="roofing",
        provenance=Provenance(
            source_type=SourceType.CLIENT_PHOTO,
            approval_status=ApprovalStatus.APPROVED,
            stage=stage,
        ),
    )


# ------------------------------------------------------------------ inference


@pytest.mark.parametrize(
    "tokens,expected",
    [
        (["roof", "bergenfield", "before", "tearoff"], "before"),
        (["roof", "hawthorne", "after", "redeck"], "after"),
        (["roof", "completed", "neighborhood"], "after"),
        (["roof", "washington", "curb", "appeal"], "after"),
        (["roof", "replacement", "in", "progress"], "during"),
        (["roof", "luxury", "estate", "gaf", "install"], "during"),
        (["roof", "cresskill", "aerial", "estate"], "neutral"),
        (["dji", "0003", "frame", "23s"], ""),
    ],
)
def test_stage_is_inferred_from_filename(repo, tokens, expected):
    assert infer_stage(tokens) == expected


def test_an_explicit_token_beats_a_weak_hint(repo):
    """'roof_bergenfield_after_aerial' is an after shot, not a neutral one."""
    assert infer_stage(["roof", "bergenfield", "after", "aerial"]) == "after"


# --------------------------------------------------------------------- policy


@pytest.mark.parametrize(
    "angle,stage,permitted",
    [
        ("premium", "after", True),
        ("premium", "neutral", True),
        ("premium", "before", False),
        ("premium", "during", False),
        ("premium", "", False),
        ("upgrade", "before", False),
        ("offer", "before", False),
        ("emotional", "before", False),
        ("problem", "before", True),
        ("problem", "after", False),
        ("urgency", "before", True),
        ("urgency", "during", True),
        ("proof", "after", True),
        ("proof", "during", True),
        ("proof", "neutral", False),
        ("education", "before", True),
        ("education", "after", True),
        ("education", "", True),
    ],
)
def test_stage_policy(repo, angle, stage, permitted):
    assert stage_permitted(_asset(stage), angle) is permitted


def test_unclassified_is_barred_from_aspirational_messages(repo):
    """An unknown state could be a tear-off, so it fails closed."""
    for angle in ("premium", "upgrade", "proof", "emotional", "offer"):
        assert stage_permitted(_asset(""), angle) is False


def test_unclassified_is_allowed_where_it_cannot_mislead(repo):
    for angle in ("education", "problem", "urgency"):
        assert stage_permitted(_asset(""), angle) is True


def test_an_unknown_angle_falls_back_to_the_safe_default(repo):
    stages, unclassified_ok = allowed_stages("no-such-angle")
    assert stages == {"after", "neutral"}
    assert unclassified_ok is False


# ------------------------------------------------------------------ selection


@pytest.fixture()
def staged_library(repo):
    approved = repo / "clients" / "testco" / "assets" / "approved"
    approved.mkdir(parents=True, exist_ok=True)
    for name, colour in [
        ("roof_bergenfield_before_tearoff_001.jpg", (70, 70, 75)),
        ("roof_bergenfield_after_architectural_001.jpg", (150, 150, 155)),
        ("roof_cresskill_aerial_estate_001.jpg", (120, 125, 130)),
    ]:
        Image.new("RGB", (1600, 1200), colour).save(approved / name)
    (repo / "data" / "assets" / "index.json").unlink(missing_ok=True)
    return AssetCatalog.load(refresh=True)


def test_a_premium_message_never_gets_a_before_photo(staged_library):
    chosen = select_asset(staged_library, "testco", "roofing", "hero-full", angle="premium")
    assert chosen is not None
    assert chosen.provenance.stage in ("after", "neutral")


def test_a_problem_message_does_get_the_worn_roof(staged_library):
    chosen = select_asset(staged_library, "testco", "roofing", "hero-full", angle="problem")
    assert chosen is not None
    assert chosen.provenance.stage in ("before", "during", "neutral")


def test_no_suitable_stage_yields_a_brand_background(repo):
    """Better no photograph than a contradictory one."""
    approved = repo / "clients" / "testco" / "assets" / "approved"
    for existing in approved.glob("*.jpg"):
        existing.unlink()
    Image.new("RGB", (1600, 1200), (70, 70, 75)).save(
        approved / "roof_bergenfield_before_tearoff_001.jpg"
    )
    (repo / "data" / "assets" / "index.json").unlink(missing_ok=True)
    catalog = AssetCatalog.load(refresh=True)
    assert select_asset(catalog, "testco", "roofing", "hero-full", angle="premium") is None


def test_no_angle_means_no_stage_filtering(staged_library):
    """Callers that do not supply an angle keep the previous behaviour."""
    assert select_asset(staged_library, "testco", "roofing", "hero-full") is not None


# ------------------------------------------------------------------- tagging


def test_stage_can_be_set_and_survives_a_reindex(repo):
    from app.assets.review import set_stage

    catalog = AssetCatalog.load(refresh=True)
    target = next(a for a in catalog.index.assets if a.production_eligible)
    set_stage(catalog, [target.id], "after")

    (repo / "data" / "assets" / "index.json").unlink(missing_ok=True)
    reloaded = AssetCatalog.load(refresh=True)
    assert reloaded.index.by_id(target.id).provenance.stage == "after"


def test_an_invalid_stage_is_rejected(repo):
    from app.assets.review import set_stage
    from app.errors import AssetError

    catalog = AssetCatalog.load(refresh=True)
    target = next(a for a in catalog.index.assets if a.production_eligible)
    with pytest.raises(AssetError, match="stage must be one of"):
        set_stage(catalog, [target.id], "finished")
