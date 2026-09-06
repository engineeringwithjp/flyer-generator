"""Tests for client manager and multi-client profiles."""

import pytest

from src.core.client_manager import ClientManager


def test_list_clients():
    mgr = ClientManager()
    clients = mgr.list_clients()
    assert "all-elite" in clients
    assert "client-002" in clients

def test_get_all_elite_client(sample_client):
    assert sample_client.id == "all-elite"
    assert "All Elite" in sample_client.company_name
    assert sample_client.brand_colors.primary_accent == "#80272B"
    assert sample_client.drive_folder_id == "12Ho15EiJumnZkSAPm0I1Zd9Vwe6CuLiT"
    assert len(sample_client.services) > 0

def test_missing_client_raises():
    mgr = ClientManager()
    with pytest.raises(FileNotFoundError):
        mgr.get_client("non-existent-contractor")
