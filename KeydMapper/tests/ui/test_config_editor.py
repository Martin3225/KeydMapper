"""Tests for the ConfigEditor UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock

from keyd.config import Config
from PySide6.QtCore import QRectF
from ui.config_editor import ConfigEditor
from ui.key_item import KeyItem


def test_config_editor_set_key_mapping():
    """Test that setting a key mapping updates the Config model correctly."""
    # Arrange
    mock_config = MagicMock(spec=Config)
    mock_config.name = "test_config"
    mock_config.layer_order = ["main"]
    mock_config.layers = {"main": {}}

    mock_scene = MagicMock()
    mock_view = MagicMock()

    editor = ConfigEditor(
        config=mock_config,
        scene=mock_scene,
        view=mock_view,
    )

    key = MagicMock(spec=KeyItem)
    key.key_name = "a"

    # Act
    editor.set_key_mapping(key, "b")

    # Assert
    assert key.key_value == "b"
    assert mock_config.layers["main"]["a"] == "b"

    # Act
    editor.set_key_mapping(key, "")

    # Assert
    assert key.key_value == ""
    assert "a" not in mock_config.layers["main"]


def test_config_editor_change_layer() -> None:
    """Test that changing the active layer updates the displayed key bindings."""
    mock_config = MagicMock(spec=Config)
    mock_config.name = "test_config"
    mock_config.layer_order = ["main", "shift"]
    mock_config.layers = {"main": {"a": "b"}, "shift": {"a": "c"}}

    mock_scene = MagicMock()
    mock_view = MagicMock()

    key = KeyItem("a", "", QRectF(0, 0, 10, 10))
    mock_scene.items.return_value = [key]

    editor = ConfigEditor(
        config=mock_config,
        scene=mock_scene,
        view=mock_view,
    )

    # Simulate activating mode (which calls _refresh_scene_values for the default 'main' layer)
    editor.activate_mode()
    assert key.key_value == "b"

    # Simulate changing layer to 'shift'
    editor._on_layer_changed("shift")
    assert key.key_value == "c"
