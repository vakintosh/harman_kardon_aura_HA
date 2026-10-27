"""Shared fixtures."""
import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow HA to load custom_components/ in tests."""
    yield
