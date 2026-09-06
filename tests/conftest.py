"""Pytest fixtures and configuration."""

import sys
from pathlib import Path

import pytest

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.core.client_manager import ClientManager
from src.core.models import ClientProfile


@pytest.fixture
def sample_client() -> ClientProfile:
    manager = ClientManager()
    return manager.get_client("all-elite")

@pytest.fixture
def sample_client_002() -> ClientProfile:
    manager = ClientManager()
    return manager.get_client("client-002")
