"""Asset provenance: placeholders must never reach a client flyer.

The failure this guards against: a synthetic image of a beautiful roof is
mistaken for a real All Elite project photograph and printed on an advert sent
to homeowners.
"""

from __future__ import annotations

import pytest
from PIL import Image

from app.assets.catalog import AssetCatalog
from app.assets.metadata import derive_provenance
from app.assets.selector import select_asset, select_pair
from app.models import ApprovalStatus, Asset, Provenance, SourceType

# ------------------------------------------------------- structural guarantee


def test_a_placeholder_cannot_be_marked_approved():
    """Enforced in the model, so no code path can promote a placeholder."""
    asset = Asset(
        id="x",
        path="assets/placeholders/fake.jpg",
        provenance=Provenance(
            source_type=SourceType.PLACEHOLDER,
            approval_status=ApprovalStatus.APPROVED,
        ),
    )
    assert asset.provenance.approval_status is ApprovalStatus.UNAPPROVED
    assert asset.production_eligible is False


def test_a_generated_sample_cannot_be_approved_either():
    asset = Asset(
        id="x",
        path="a.jpg",
        provenance=Provenance(
            source_type=SourceType.GENERATED_SAMPLE,
            approval_status=ApprovalStatus.APPROVED,
        ),
    )
    assert asset.production_eligible is False


def test_unknown_provenance_fails_closed():
    assert Asset(id="x", path="a.jpg").production_eligible is False


def test_real_client_media_can_be_production_eligible():
    asset = Asset(
        id="x",
        path="clients/c/assets/approved/roof.jpg",
        provenance=Provenance(
            source_type=SourceType.CLIENT_PHOTO,
            approval_status=ApprovalStatus.APPROVED,
        ),
    )
    assert asset.production_eligible is True


def test_real_media_still_needs_approval():
    """Raw drone footage is real, but not automatically publishable."""
    asset = Asset(
        id="x",
        path="clients/c/assets/raw/drone/DJI_0001.JPG",
        provenance=Provenance(
            source_type=SourceType.CLIENT_DRONE,
            approval_status=ApprovalStatus.UNAPPROVED,
        ),
    )
    assert asset.production_eligible is False


@pytest.mark.parametrize(
    "source,expected",
    [
        (SourceType.CLIENT_PHOTO, 100),
        (SourceType.CLIENT_DRONE, 95),
        (SourceType.CLIENT_VIDEO_FRAME, 90),
        (SourceType.INTERNAL_BACKGROUND, 70),
        (SourceType.STOCK, 45),
        (SourceType.PLACEHOLDER, 0),
        (SourceType.UNKNOWN, 0),
    ],
)
def test_source_ranking_puts_real_client_media_first(source, expected):
    assert Provenance(source_type=source).rank == expected


# ------------------------------------------------------------- path inference


def test_placeholder_folder_is_detected(repo):
    path = repo / "assets" / "placeholders" / "roofing" / "placeholder-roof.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 600), (120, 130, 140)).save(path)
    provenance = derive_provenance(path)
    assert provenance["source_type"] == SourceType.PLACEHOLDER
    assert provenance["approval_status"] == ApprovalStatus.UNAPPROVED


def test_client_approved_folder_is_detected(repo):
    path = repo / "clients" / "testco" / "assets" / "approved" / "roof_bergenfield_after_01.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 600), (100, 110, 120)).save(path)
    provenance = derive_provenance(path)
    assert provenance["source_type"] == SourceType.CLIENT_PHOTO
    assert provenance["approval_status"] == ApprovalStatus.APPROVED
    assert provenance["project"] == "bergenfield"
    assert provenance["stage"] == "after"


def test_raw_client_media_is_real_but_unapproved(repo):
    path = repo / "clients" / "testco" / "assets" / "raw" / "drone" / "DJI_0042.JPG"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 600), (100, 110, 120)).save(path)
    provenance = derive_provenance(path)
    assert provenance["source_type"] == SourceType.CLIENT_DRONE
    assert provenance["approval_status"] == ApprovalStatus.UNAPPROVED


def test_extracted_frames_are_classified_as_frames(repo):
    path = repo / "clients" / "testco" / "assets" / "raw" / "frames" / "DJI_0001_frame_2.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 600), (100, 110, 120)).save(path)
    assert derive_provenance(path)["source_type"] == SourceType.CLIENT_VIDEO_FRAME


def test_the_client_slug_is_never_used_as_a_project_label(repo):
    """Regression: every photo was labelled project='all-elite', which broke
    before/after pairing by mixing two different houses."""
    path = repo / "clients" / "testco" / "assets" / "approved" / "roof_generic_001.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 600), (100, 110, 120)).save(path)
    assert derive_provenance(path)["project"] != "testco"


# ------------------------------------------------------------- selection gate


@pytest.fixture()
def placeholder_only(repo):
    """A library containing nothing but synthetic images."""
    import shutil

    for folder in ("roofing", "siding"):
        shutil.rmtree(repo / "assets" / folder, ignore_errors=True)
    shutil.rmtree(repo / "clients" / "testco" / "assets" / "approved", ignore_errors=True)

    path = repo / "assets" / "placeholders" / "roofing" / "placeholder-roof.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1600, 1200), (120, 130, 140)).save(path)
    (repo / "data" / "assets" / "index.json").unlink(missing_ok=True)
    return AssetCatalog.load(refresh=True)


def test_a_placeholder_is_never_selected_for_production(placeholder_only):
    assert select_asset(placeholder_only, "testco", "roofing", "hero-full") is None


def test_a_placeholder_is_available_in_development_mode(placeholder_only):
    chosen = select_asset(
        placeholder_only, "testco", "roofing", "hero-full", allow_non_production=True
    )
    assert chosen is not None and chosen.is_synthetic


def test_a_flyer_with_only_placeholders_uses_a_brand_background(placeholder_only, repo):
    """The whole point: no photograph beats a fake photograph."""
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=1, upload=False)
    assert run.succeeded == 1
    assert run.results[0].spec.image.asset_id is None


def test_real_client_photos_are_selected_when_present(repo):
    catalog = AssetCatalog.load(refresh=True)
    chosen = select_asset(catalog, "testco", "roofing", "hero-full")
    assert chosen is not None
    assert chosen.production_eligible


def test_the_catalog_reports_what_it_blocked(repo):
    path = repo / "assets" / "placeholders" / "x" / "placeholder-a.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (900, 700), (110, 120, 130)).save(path)
    catalog = AssetCatalog.load(refresh=True)
    blocked = [a for a in catalog.index.assets if not a.production_eligible]
    assert any(a.is_synthetic for a in blocked)


# ------------------------------------------------------- honest before/after


def test_a_before_after_pair_comes_from_one_project(repo):
    approved = repo / "clients" / "testco" / "assets" / "approved"
    approved.mkdir(parents=True, exist_ok=True)
    for name, colour in [
        ("roof_bergenfield_before_001.jpg", (90, 90, 95)),
        ("roof_bergenfield_after_001.jpg", (150, 150, 155)),
        ("roof_hawthorne_before_001.jpg", (80, 85, 90)),
        ("roof_hawthorne_after_001.jpg", (160, 160, 165)),
    ]:
        Image.new("RGB", (1600, 1200), colour).save(approved / name)
    (repo / "data" / "assets" / "index.json").unlink(missing_ok=True)

    catalog = AssetCatalog.load(refresh=True)
    before, after = select_pair(catalog, "testco", "roofing", "before-after")
    assert before is not None and after is not None
    assert before.provenance.project == after.provenance.project
    assert before.provenance.stage == "before"
    assert after.provenance.stage == "after"
