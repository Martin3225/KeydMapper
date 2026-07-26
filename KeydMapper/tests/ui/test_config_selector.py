"""Tests for the ConfigSelector UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock, patch

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
@patch("ui.config_selector.get_device_id_from_config", return_value="1234:5678")
def test_config_selector_displays_all_configs(
    _mock_device_id, mock_listdir
) -> None:
    """Test that valid configurations are displayed as compact rows."""
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
    filenames = [row.filename for row in selector.config_rows]

    assert selector.new_config_btn.text() == "+ New config"
    assert filenames == ["another.conf", "config1.conf", "config2.disabled"]
    assert "not_a_config.txt" not in filenames


@patch("ui.config_selector.os.listdir", return_value=[])
def test_config_selector_has_minimal_empty_state(_mock_listdir) -> None:
    """An empty installation offers one primary creation action."""
    selector = ConfigSelector()

    assert not selector.config_rows
    assert "No configurations yet" in selector.list_layout.itemAt(0).widget().text()
    assert selector.new_config_btn.isEnabled() is True
