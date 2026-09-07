"""Disk hygiene: nothing irreplaceable is ever deleted."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from PIL import Image

from app.storage import (
    directory_size,
    downscale_image,
    downscale_library,
    human,
    prune_output,
    prune_unreviewed_frames,
    usage,
)


def _run_folder(repo, when: date, uploaded: bool = True, count: int = 2):
    folder = repo / "output" / when.isoformat() / "testco"
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        image = folder / f"flyer-{index:02d}.png"
        Image.new("RGB", (1080, 1350), (40, 50, 60)).save(image)
        (folder / f"flyer-{index:02d}.json").write_text(
            json.dumps({"drive_file_id": "abc123" if uploaded else ""}), encoding="utf-8"
        )
    return folder


# ------------------------------------------------------------------- helpers


@pytest.mark.parametrize(
    "size,expected",
    [(0, "0 B"), (2048, "2 KB"), (5 * 1024**2, "5.0 MB"), (3 * 1024**3, "3.0 GB")],
)
def test_human_readable_sizes(size, expected):
    assert human(size) == expected


def test_directory_size_of_a_missing_path_is_zero(repo, tmp_path):
    assert directory_size(tmp_path / "nope") == 0


# -------------------------------------------------------------------- output


def test_old_uploaded_runs_are_removed(repo):
    old = _run_folder(repo, date.today() - timedelta(days=30), uploaded=True)
    report = prune_output(keep_days=7)
    assert report.output_runs_removed == 1
    assert not old.exists()
    assert report.freed_bytes > 0


def test_recent_runs_are_kept(repo):
    recent = _run_folder(repo, date.today() - timedelta(days=1), uploaded=True)
    assert prune_output(keep_days=7).output_runs_removed == 0
    assert recent.exists()


def test_an_un_uploaded_run_is_never_deleted(repo):
    """Deleting the only copy of something is the one unrecoverable mistake."""
    orphan = _run_folder(repo, date.today() - timedelta(days=60), uploaded=False)
    report = prune_output(keep_days=7)
    assert report.output_runs_removed == 0
    assert orphan.exists()
    assert any("not in Drive" in d for d in report.details)


def test_a_partially_uploaded_run_is_kept(repo):
    folder = _run_folder(repo, date.today() - timedelta(days=30), uploaded=True, count=2)
    (folder / "flyer-02.json").write_text(json.dumps({"drive_file_id": ""}), encoding="utf-8")
    assert prune_output(keep_days=7).output_runs_removed == 0
    assert folder.exists()


def test_dry_run_deletes_nothing(repo):
    old = _run_folder(repo, date.today() - timedelta(days=30))
    report = prune_output(keep_days=7, dry_run=True)
    assert report.output_runs_removed == 1
    assert report.freed_bytes > 0
    assert old.exists()


def test_non_date_folders_are_left_alone(repo):
    keep = repo / "output" / "_layouts"
    keep.mkdir(parents=True)
    Image.new("RGB", (100, 100)).save(keep / "x.png")
    prune_output(keep_days=0)
    assert keep.exists()


# ------------------------------------------------------------------ downscale


def test_a_large_image_is_downscaled(repo, tmp_path):
    path = tmp_path / "big.jpg"
    Image.new("RGB", (4056, 3040), (120, 130, 140)).save(path, quality=95)
    before = path.stat().st_size
    saved = downscale_image(path, max_edge=2400)
    with Image.open(path) as image:
        assert max(image.size) == 2400
    assert saved > 0
    assert path.stat().st_size < before


def test_a_small_image_is_untouched(repo, tmp_path):
    path = tmp_path / "small.jpg"
    Image.new("RGB", (800, 600), (120, 130, 140)).save(path)
    before = path.stat().st_size
    assert downscale_image(path, max_edge=2400) == 0
    assert path.stat().st_size == before


def test_downscaled_images_still_cover_the_flyer_canvas(repo, tmp_path):
    """2400px must survive a 4:5 crop at 1080x1350 with no upscaling."""
    from app.assets.image_utils import crop_to_aspect

    path = tmp_path / "frame.jpg"
    Image.new("RGB", (3840, 2160), (100, 110, 120)).save(path)
    downscale_image(path, max_edge=2400)
    with Image.open(path) as image:
        assert image.height >= 1350, "must not need upscaling for a 1080x1350 flyer"
        cropped = crop_to_aspect(image.convert("RGB"), 1080, 1350)
    assert cropped.size == (1080, 1350)


def test_logos_are_never_downscaled(repo):
    logo = repo / "clients" / "testco" / "assets" / "logo" / "logo.png"
    logo.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (3000, 900), (255, 0, 0, 255)).save(logo)
    downscale_library(max_edge=800)
    with Image.open(logo) as image:
        assert image.width == 3000


# ------------------------------------------------------------- raw candidates


def test_weak_candidates_are_pruned_and_good_ones_kept(repo):
    from app.assets.catalog import AssetCatalog

    frames = repo / "clients" / "testco" / "assets" / "raw" / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for index in range(6):
        name = f"dji_{index:04d}_frame_10s"
        Image.new("RGB", (1600, 1200), (100 + index, 110, 120)).save(frames / f"{name}.jpg")
        (frames / f"{name}.json").write_text(
            json.dumps({"quality_score": index / 10}), encoding="utf-8"
        )
    (repo / "data" / "assets" / "index.json").unlink(missing_ok=True)
    AssetCatalog.load(refresh=True)

    report = prune_unreviewed_frames(keep_top=2)
    assert report.frames_removed == 4
    remaining = sorted(p.stem for p in frames.glob("*.jpg"))
    assert remaining == ["dji_0004_frame_10s", "dji_0005_frame_10s"]


def test_approved_assets_are_never_pruned(repo):
    from app.assets.catalog import AssetCatalog

    approved = repo / "clients" / "testco" / "assets" / "approved"
    before = sorted(p.name for p in approved.glob("*.jpg"))
    AssetCatalog.load(refresh=True)
    prune_unreviewed_frames(keep_top=0)
    assert sorted(p.name for p in approved.glob("*.jpg")) == before


# --------------------------------------------------------------------- usage


def test_usage_reports_every_area(repo):
    areas = usage()
    for key in (
        "output (rendered flyers)",
        "approved photography",
        "unreviewed candidates",
        "git history",
        "python environment",
    ):
        assert key in areas
        assert areas[key] >= 0


def test_original_stills_are_never_pruned(repo):
    """Regression: `flyer clean` deleted 17 high-res drone originals because
    they were unreviewed and unscored. Only extracted frames are regenerable."""
    import json

    from app.assets.catalog import AssetCatalog

    drone = repo / "clients" / "testco" / "assets" / "raw" / "drone"
    drone.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4056, 3040), (100, 110, 120)).save(drone / "DJI_0005.JPG")

    frames = repo / "clients" / "testco" / "assets" / "raw" / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for index in range(3):
        name = f"dji_{index:04d}_frame_10s"
        Image.new("RGB", (1600, 1200), (100 + index, 110, 120)).save(frames / f"{name}.jpg")
        (frames / f"{name}.json").write_text(
            json.dumps({"quality_score": index / 10}), encoding="utf-8"
        )

    (repo / "data" / "assets" / "index.json").unlink(missing_ok=True)
    AssetCatalog.load(refresh=True)

    prune_unreviewed_frames(keep_top=0)
    assert (drone / "DJI_0005.JPG").exists(), "an original still must survive"
    assert not list(frames.glob("*.jpg")), "extracted frames are regenerable and may go"
