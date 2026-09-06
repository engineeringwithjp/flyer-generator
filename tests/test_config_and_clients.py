"""Configuration loading and client-profile validation."""

from __future__ import annotations

import json

import pytest

from app.clients.loader import list_clients, load_client
from app.clients.validator import validate_client
from app.config import get_settings, load_json_config
from app.errors import ClientError


def test_settings_use_the_temp_root(repo):
    assert get_settings().paths.root == repo


def test_settings_describe_never_leaks_secrets(repo, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-super-secret-value")
    from app.config import reset_settings_cache

    reset_settings_cache()
    described = json.dumps(get_settings().describe())
    assert "super-secret" not in described


def test_load_client_round_trips(client):
    assert client.id == "testco"
    assert client.company_name == "Testco Roofing LLC"
    assert "Roofing" in client.services
    assert client.brand.primary == "#12243A"
    assert client.brand.accent == "#E0A62F"


def test_missing_client_raises_with_a_useful_message(repo):
    with pytest.raises(ClientError) as excinfo:
        load_client("does-not-exist")
    assert "Available" in str(excinfo.value)


def test_client_folder_name_must_match_id(repo):
    (repo / "clients/mismatch").mkdir(parents=True)
    (repo / "clients/mismatch/client.json").write_text(
        json.dumps({"id": "other", "company_name": "X"}), encoding="utf-8"
    )
    with pytest.raises(ClientError, match="does not match folder name"):
        load_client("mismatch")


def test_invalid_json_raises_client_error(repo):
    (repo / "clients/broken").mkdir(parents=True)
    (repo / "clients/broken/client.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ClientError, match="not valid JSON"):
        load_client("broken")


def test_list_clients_skips_the_template(repo):
    (repo / "clients/_template").mkdir(parents=True)
    (repo / "clients/_template/client.json").write_text(
        json.dumps({"id": "_template", "company_name": "T"}), encoding="utf-8"
    )
    assert [c.id for c in list_clients()] == ["testco"]


def test_valid_client_passes_validation(client):
    result = validate_client(client)
    assert result.passed, [str(i) for i in result.issues]


def test_client_with_no_contact_fails_validation(client):
    broken = client.model_copy(deep=True)
    broken.contact.phone = ""
    broken.contact.website = ""
    broken.contact.email = ""
    result = validate_client(broken)
    assert not result.passed
    assert any(i.check == "contact" for i in result.issues)


def test_client_with_no_services_fails_validation(client):
    broken = client.model_copy(deep=True)
    broken.services = []
    assert not validate_client(broken).passed


def test_bad_hex_colour_is_rejected(client):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        client.brand.model_copy(update={}).model_validate(
            {**client.brand.model_dump(), "primary_colors": ["not-a-colour"]}
        )


def test_adding_a_client_needs_no_code_change(repo):
    """SUCCESS CRITERION 14: a new contractor is configuration, not code."""
    (repo / "clients/second-co/assets/approved").mkdir(parents=True)
    (repo / "clients/second-co/client.json").write_text(
        json.dumps(
            {
                "id": "second-co",
                "company_name": "Second Co Exteriors",
                "services": ["Siding"],
                "contact": {"phone": "(201) 555-0199"},
                "brand": {"primary_colors": ["#203040"], "secondary_colors": ["#D08010"]},
            }
        ),
        encoding="utf-8",
    )
    assert {c.id for c in list_clients()} == {"testco", "second-co"}
    assert validate_client(load_client("second-co")).passed


def test_config_catalogues_are_valid_json(repo):
    for name in ("campaigns.json", "scoring.json", "layouts.json", "typography.json"):
        assert isinstance(load_json_config(name), dict)


def test_scoring_weights_sum_to_one(repo):
    weights = load_json_config("scoring.json")["weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    asset_weights = load_json_config("scoring.json")["asset_weights"]
    assert abs(sum(asset_weights.values()) - 1.0) < 1e-9
