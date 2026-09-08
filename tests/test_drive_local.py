"""Writing flyers straight into a mounted Google Drive folder."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.config import reset_settings_cache
from app.drive.local import describe, find_folder, is_available, resolve_output_dir


@pytest.fixture()
def mounted(repo, monkeypatch):
    """A stand-in for a Google Drive for Desktop mount."""
    mount = repo / "fake-drive" / "My Drive" / "NEDA" / "Client Flyers"
    mount.mkdir(parents=True)
    monkeypatch.setenv("DRIVE_LOCAL_PATH", str(mount))
    reset_settings_cache()
    return mount


def test_not_available_when_unset(repo):
    assert is_available() is False


def test_available_when_the_folder_exists(mounted):
    assert is_available() is True


def test_not_available_when_the_path_is_wrong(repo, monkeypatch):
    monkeypatch.setenv("DRIVE_LOCAL_PATH", str(repo / "no-such-folder"))
    reset_settings_cache()
    assert is_available() is False


def test_output_dir_mirrors_the_api_layout(mounted):
    target = resolve_output_dir("All Elite Roofing & Siding", date(2026, 9, 6))
    assert target is not None
    assert target.relative_to(mounted).parts == ("Flyers", "2026", "September", "09-06")
    assert target.is_dir()


def test_output_dir_matches_the_uploader_segments(mounted):
    """Both delivery paths must produce the same tree in Drive."""
    from app.drive.folders import flyer_folder_path

    api = flyer_folder_path("All Elite Roofing & Siding", date(2026, 9, 6))[1:]
    local = resolve_output_dir("All Elite Roofing & Siding", date(2026, 9, 6))
    assert list(local.relative_to(mounted).parts) == api


def test_output_dir_is_none_without_configuration(repo):
    assert resolve_output_dir("Any Co", date(2026, 9, 6)) is None


def test_a_vanished_mount_degrades_instead_of_crashing(repo, monkeypatch):
    """Drive for Desktop may be quit; the run must still produce flyers."""
    monkeypatch.setenv("DRIVE_LOCAL_PATH", str(repo / "gone"))
    reset_settings_cache()
    assert resolve_output_dir("Any Co", date(2026, 9, 6)) is None


def test_find_folder_returns_none_when_absent(repo):
    assert find_folder("Definitely Not A Real Folder Name Here") is None


def test_describe_reports_configuration(mounted):
    info = describe()
    assert info["configured_exists"] is True
    assert "Stream files" in info["streaming_hint"]


# --------------------------------------------------------------- pipeline


def test_a_delivered_flyer_ends_up_in_drive_and_not_the_project(mounted, repo):
    """The end state the client sees: flyers in Drive, nothing left behind."""
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=1, upload=True, when=date(2026, 9, 6))
    assert run.results
    assert run.results[0].qa_passed, run.results[0].rejection_reasons

    written = run.results[0].image_path
    assert str(mounted) in written, "a passing flyer belongs in the Drive mount"
    assert not list((repo / "output").rglob("flyer-*.png")), "nothing left in the project output/"


def test_rendering_stages_locally_before_anything_reaches_drive(mounted, repo):
    """Rendering must never put an unreviewed flyer in front of the client.

    ``upload=False`` is the dry run, and it has to leave Drive untouched -
    this is the regression guard for the bug where the renderer wrote straight
    into the client's folder and QA could only report a failure after the
    client could already see it.
    """
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=1, upload=False, when=date(2026, 9, 6))
    assert run.results
    assert str(repo / "output") in run.results[0].image_path
    assert not list(mounted.rglob("flyer-*.png")), "dry run must not touch Drive"


def test_a_flyer_that_fails_qa_is_held_back_from_drive(mounted, repo):
    """The gate itself: a failing flyer stays in staging."""
    from app.models import GenerationRun
    from app.pipeline.deliver import deliver
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=1, upload=False, when=date(2026, 9, 6))
    result = run.results[0]
    result.qa_passed = False
    result.rejection_reasons = ["deliberately failed for this test"]

    held_run = GenerationRun(run_id="held", client_id="testco", date="2026-09-06", results=[result])
    from app.clients.loader import load_client

    report = deliver(held_run, load_client("testco"), date(2026, 9, 6))

    assert report.delivered == []
    assert report.held and report.held[0][0] == result.spec.id
    assert not list(mounted.rglob("flyer-*.png")), "a failing flyer must never reach Drive"
    assert Path(result.image_path).exists(), "it should still be in staging for inspection"


def test_a_duplicate_photograph_blocks_the_second_flyer(repo):
    """Two flyers on the same photo is a batch failure, not two good flyers."""
    from app.pipeline.deliver import batch_issues
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=2, upload=False, when=date(2026, 9, 6))
    first, second = run.results
    second.spec.image.asset_id = first.spec.image.asset_id = "same-photo"

    issues = batch_issues([first, second])
    assert not issues[first.spec.id], "the first use is fine"
    assert any(i.check == "duplicate_photo" for i in issues[second.spec.id])


def test_the_project_is_used_when_drive_is_not_configured(repo):
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=1, upload=False, when=date(2026, 9, 6))
    assert "output" in run.results[0].image_path
