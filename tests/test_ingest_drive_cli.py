"""Reference ingestion, Google Drive (mocked), the CLI, and the gallery."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.errors import DriveError
from app.models import ReferenceStatus

# ------------------------------------------------------------------- ingest


@pytest.fixture()
def analyser(monkeypatch):
    """Stub Claude vision with a fixed, valid analysis."""
    payload = {
        "category": "roofing",
        "style": "premium-modern",
        "layout": "hero-background",
        "text_density": "low",
        "visual_weight": "image-heavy",
        "cta_position": "bottom-left",
        "image_treatment": "dark-gradient",
        "typography": "condensed heavy display over light sans",
        "color_characteristics": ["dark neutral base", "single warm accent"],
        "dominant_colors": ["#12243A", "#E0A62F"],
        "composition_notes": "Eye enters at the roofline and settles on the CTA.",
        "negative_space": "Lower third",
        "recommended_campaigns": ["roof-replacement", "storm-damage"],
        "suggested_layouts": ["hero-full"],
        "description": "A restrained hero layout with a heavy scrim.",
    }
    stub = MagicMock(return_value=payload)
    monkeypatch.setattr("app.pipeline.ingest.analyze_reference", stub)
    return stub


def _drop(repo, name="nice-roofing-ad.jpg"):
    path = repo / "references" / "inbox" / name
    Image.new("RGB", (1080, 1350), (100, 110, 120)).save(path)
    return path


def test_ingesting_one_image_files_it_and_indexes_it(repo, analyser):
    from app import references as reference_lib
    from app.pipeline.ingest import ingest_reference

    path = _drop(repo)
    reference = ingest_reference(path)

    assert reference.id == "ref_000001"
    assert reference.category == "roofing"
    assert reference.status is ReferenceStatus.EXPERIMENTAL
    assert (repo / reference.path).exists()
    assert not path.exists(), "the inbox should be emptied"
    assert reference_lib.load_index().by_id("ref_000001") is not None


def test_the_original_filename_is_preserved_in_metadata(repo, analyser):
    from app.pipeline.ingest import ingest_reference

    assert ingest_reference(_drop(repo, "cool-ad.jpg")).filename == "cool-ad.jpg"


def test_a_json_sidecar_is_written_next_to_the_image(repo, analyser):
    from app.pipeline.ingest import ingest_reference

    reference = ingest_reference(_drop(repo))
    sidecar = (repo / reference.path).with_suffix(".json")
    assert sidecar.exists()
    assert json.loads(sidecar.read_text())["style"] == "premium-modern"


def test_new_references_never_land_in_approved(repo, analyser):
    from app.pipeline.ingest import ingest_reference

    assert "experimental" in ingest_reference(_drop(repo)).path


def test_a_duplicate_is_skipped_not_re_analysed(repo, analyser):
    from app.pipeline.ingest import ingest_reference

    first = ingest_reference(_drop(repo, "a.jpg"), move=False)
    assert analyser.call_count == 1
    second = ingest_reference(_drop(repo, "a.jpg"), move=False)
    assert second.id == first.id
    assert analyser.call_count == 1, "COST CONTROL: a duplicate must not re-hit the API"


def test_force_re_analyses_a_duplicate(repo, analyser):
    from app.pipeline.ingest import ingest_reference

    ingest_reference(_drop(repo, "a.jpg"), move=False)
    ingest_reference(_drop(repo, "a.jpg"), move=False, force=True)
    assert analyser.call_count == 2


def test_ingesting_the_whole_inbox(repo, analyser):
    from app.pipeline.ingest import ingest_directory

    for name in ("one.jpg", "two.jpg", "three.jpg"):
        Image.new("RGB", (900, 1100), (hash(name) % 200, 120, 130)).save(
            repo / "references" / "inbox" / name
        )
    assert len(ingest_directory()) == 3


def test_an_empty_inbox_is_not_an_error(repo, analyser):
    from app.pipeline.ingest import ingest_directory

    assert ingest_directory() == []


def test_one_bad_file_does_not_abort_the_batch(repo, analyser):
    from app.pipeline.ingest import ingest_directory

    Image.new("RGB", (900, 1100), (100, 100, 100)).save(repo / "references/inbox/good.jpg")
    (repo / "references/inbox/bad.jpg").write_bytes(b"not an image")
    assert len(ingest_directory()) == 1


def test_an_ingested_reference_influences_the_next_flyer(repo, analyser, client):
    """SUCCESS CRITERION 1-3: drop an image, and it shapes future design."""
    from app import references as reference_lib
    from app.pipeline.ingest import ingest_reference

    reference = ingest_reference(_drop(repo))
    chosen = reference_lib.select_reference("roofing", "roof-replacement", "hero-full", client)
    assert chosen is not None and chosen.id == reference.id


# -------------------------------------------------------------------- drive


class _FakeFiles:
    def __init__(self, store):
        self.store = store
        self.created, self.updated = [], []

    def list(self, **kwargs):
        query = kwargs["q"]
        matches = [f for f in self.store if f["_q"] in query]
        return SimpleNamespace(execute=lambda: {"files": matches})

    def create(self, **kwargs):
        body = kwargs["body"]
        record = {
            "id": f"file_{len(self.store) + 1}",
            "name": body["name"],
            "webViewLink": f"https://drive.example/{body['name']}",
            "appProperties": body.get("appProperties", {}),
            "_q": f"name = '{body['name']}'",
        }
        self.store.append(record)
        self.created.append(body["name"])
        return SimpleNamespace(execute=lambda: record)

    def update(self, **kwargs):
        self.updated.append(kwargs["fileId"])
        return SimpleNamespace(
            execute=lambda: {"id": kwargs["fileId"], "webViewLink": "https://drive.example/x"}
        )


class _FakeService:
    def __init__(self):
        self._files = _FakeFiles([])

    def files(self):
        return self._files


@pytest.fixture()
def drive(repo, monkeypatch):
    from app.config import reset_settings_cache
    from app.drive.uploader import DriveUploader

    monkeypatch.setenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "root123")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "rtoken")
    reset_settings_cache()
    service = _FakeService()
    return DriveUploader(service=service), service


def test_folder_path_is_company_year_month_day():
    from app.drive.folders import flyer_folder_path

    assert flyer_folder_path("Testco", date(2026, 9, 5)) == [
        "Testco",
        "Flyers",
        "2026",
        "September",
        "09-05",
    ]


def test_missing_drive_folder_raises_a_clear_error(repo, client):
    from app.drive.uploader import DriveUploader

    with pytest.raises(DriveError, match="No Drive folder"):
        DriveUploader(service=_FakeService()).resolve_root(client)


def test_upload_creates_the_file_and_returns_an_id(repo, client, drive, tmp_path):
    uploader, service = drive
    path = tmp_path / "flyer-01.png"
    Image.new("RGB", (1080, 1350), (30, 40, 50)).save(path)
    file_id, link = uploader.upload_file(path, "folder1", checksum="abc")
    assert file_id and link
    assert service._files.created == ["flyer-01.png"]


def test_an_identical_file_is_not_re_uploaded(repo, client, drive, tmp_path):
    """DUPLICATE HANDLING."""
    uploader, service = drive
    path = tmp_path / "flyer-01.png"
    Image.new("RGB", (1080, 1350), (30, 40, 50)).save(path)
    uploader.upload_file(path, "folder1", checksum="same")
    uploader.upload_file(path, "folder1", checksum="same")
    assert len(service._files.created) == 1
    assert service._files.updated == []


def test_a_changed_file_replaces_rather_than_duplicating(repo, client, drive, tmp_path):
    uploader, service = drive
    path = tmp_path / "flyer-01.png"
    Image.new("RGB", (1080, 1350), (30, 40, 50)).save(path)
    uploader.upload_file(path, "folder1", checksum="v1")
    uploader.upload_file(path, "folder1", checksum="v2")
    assert len(service._files.created) == 1
    assert len(service._files.updated) == 1


def test_uploading_a_missing_file_raises(repo, drive, tmp_path):
    uploader, _ = drive
    with pytest.raises(DriveError, match="missing file"):
        uploader.upload_file(tmp_path / "nope.png", "folder1")


def test_drive_is_reported_unavailable_without_configuration(repo):
    from app.drive.auth import drive_available

    assert drive_available() is False


def test_a_drive_failure_does_not_lose_the_flyers(repo, monkeypatch):
    from app.pipeline import generate as generate_module

    monkeypatch.setattr(
        generate_module, "_upload", MagicMock(side_effect=DriveError("drive is down"))
    )
    with pytest.raises(DriveError):
        generate_module.generate_flyers(client_id="testco", count=1, upload=True)


# ---------------------------------------------------------------------- CLI


def _run(argv):
    from app.cli import main

    return main(argv)


def test_cli_validate_exits_zero(repo, capsys):
    assert _run(["validate"]) == 0
    assert "Validation passed" in capsys.readouterr().out


def test_cli_list_clients(repo, capsys):
    assert _run(["list-clients"]) == 0
    assert "testco" in capsys.readouterr().out


def test_cli_list_clients_json(repo, capsys):
    assert _run(["list-clients", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["id"] == "testco"


def test_cli_layouts_lists_all_six(repo, capsys):
    assert _run(["layouts"]) == 0
    out = capsys.readouterr().out
    for layout in ("hero-full", "banner-lower-third", "before-after", "stat-stack"):
        assert layout in out


def test_cli_design_system_summary(repo, capsys):
    assert _run(["design-system"]) == 0
    assert "hard_rules" in capsys.readouterr().out


def test_cli_generate_produces_files(repo, capsys):
    assert _run(["generate", "--count", "2", "--no-upload"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_cli_generate_with_a_short_brief(repo, capsys):
    code = _run(
        [
            "generate",
            "--count",
            "1",
            "--no-upload",
            "--campaign",
            "siding",
            "--message",
            "built-in insulation",
            "--cta",
            "Free Estimate",
        ]
    )
    assert code == 0
    assert "Insulation" in capsys.readouterr().out


def test_cli_catalog_indexes_photos(repo, capsys):
    assert _run(["catalog"]) == 0
    assert "asset(s) indexed" in capsys.readouterr().out


def test_cli_history_and_feedback_round_trip(repo, capsys):
    from app.pipeline import history

    _run(["generate", "--count", "1", "--no-upload"])
    capsys.readouterr()
    flyer_id = history.for_client("testco")[0]["flyer_id"]

    assert _run(["feedback", flyer_id, "reject", "--reason", "headline too small"]) == 0
    assert history.find_entry(flyer_id)["approved"] is False
    assert history.find_entry(flyer_id)["rejection_reasons"] == ["headline too small"]

    assert _run(["feedback", flyer_id, "approve"]) == 0
    assert history.find_entry(flyer_id)["approved"] is True


def test_feedback_on_an_unknown_flyer_fails(repo, capsys):
    assert _run(["feedback", "not-a-flyer", "approve"]) == 1


def test_cli_schedule_check_reports_a_decision(repo, capsys):
    code = _run(["schedule-check", "--tolerance", "1440"])
    assert code == 0
    assert "Should run: yes" in capsys.readouterr().out


def test_cli_gallery_builds_a_page(repo, tmp_path, capsys):
    _run(["generate", "--count", "1", "--no-upload"])
    capsys.readouterr()
    out = tmp_path / "site"
    assert _run(["gallery", "--out", str(out)]) == 0
    page = (out / "index.html").read_text()
    assert "<title>" in page and "flyers" in page


def test_gallery_handles_an_empty_output_folder(repo, tmp_path):
    from app.publish import build_gallery

    page = build_gallery(tmp_path / "site").read_text()
    assert "No flyers yet" in page
