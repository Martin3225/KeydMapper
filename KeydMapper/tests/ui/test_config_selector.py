"""Tests for the ConfigSelector UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QPushButton
from ui.config_selector import ConfigSelector


@patch("ui.config_selector.os.listdir")
def test_config_selector_open_existing_config(mock_listdir) -> None:
    """Test that selecting an existing config emits open_editor_requested signal."""
    # Arrange
    mock_listdir.return_value = ["myconfig.conf"]

    selector = ConfigSelector()
    selector.open_editor_requested = MagicMock()

    # Act
    selector._config_click("myconfig.conf")

    # Assert
    selector.open_editor_requested.emit.assert_called_once_with("myconfig.conf", None)


@patch("ui.config_selector.os.listdir")
def test_config_selector_displays_all_configs(mock_listdir) -> None:
    """Test that all valid configurations are displayed as buttons."""
    # Arrange
    mock_listdir.return_value = [
        "config1.conf",
        "config2.disabled",
        "not_a_config.txt",
        "another.conf",
    ]

    # Act
    selector = ConfigSelector()

    # Assert
    # "New config", "config1.conf", "config2.disabled", "another.conf"
    assert selector.grid_layout.count() == 4

    button_texts = []
    for i in range(selector.grid_layout.count()):
        item = selector.grid_layout.itemAt(i)
        if item is not None:
            widget = item.widget()
            if isinstance(widget, QPushButton):
                button_texts.append(widget.text())

    assert "New config" in button_texts
    assert "config1.conf" in button_texts
    assert "config2.disabled" in button_texts
    assert "another.conf" in button_texts
    assert "not_a_config.txt" not in button_texts
