"""Global pytest fixtures for KeydMapper tests."""

import sys

import pytest
from PySide6.QtWidgets import QApplication


# @generated [all] Gemini 3.1: Fix test for PySide6 crashing
@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Provides a global QApplication instance for UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
