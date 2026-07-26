"""Tests for the ChangeLayerAction UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock, patch

from ui.actions.change_layer import ChangeLayerAction
from ui.key_item import KeyItem


def _create_mock_editor():
    mock_editor = MagicMock()
    mock_config = MagicMock()
    mock_config.layers = {"main": {}}
    mock_config.layer_order = ["main"]
    mock_editor.config = mock_config
    mock_editor.layer_combo = MagicMock()
    mock_editor._current_layer = "main"
    return mock_editor


def test_new_layer_parsing_valid_mod():
    """Test that creating a layer with a valid modifier keeps the modifier."""
    mock_editor = _create_mock_editor()
    action = ChangeLayerAction(mock_editor)

    with patch(
        "ui.actions.change_layer.QInputDialog.getText", return_value=("nav:C", True)
    ):
        action._create_new_layer()

    assert "nav:C" in mock_editor.config.layers
    assert "nav:C" in mock_editor.config.layer_order
    mock_editor.layer_combo.addItem.assert_called_with("nav:C")


def test_new_layer_parsing_invalid_mod():
    """Test that creating a layer with an invalid modifier drops the modifier."""
    mock_editor = _create_mock_editor()
    action = ChangeLayerAction(mock_editor)

    with patch(
        "ui.actions.change_layer.QInputDialog.getText", return_value=("nav:Xgg", True)
    ):
        action._create_new_layer()

    assert "nav" in mock_editor.config.layers
    assert "nav:X" not in mock_editor.config.layers


def test_new_layer_parsing_chained_mods():
    """Test that creating a layer with chained modifiers extracts the first valid one."""
    mock_editor = _create_mock_editor()
    action = ChangeLayerAction(mock_editor)

    with patch(
        "ui.actions.change_layer.QInputDialog.getText",
        return_value=("nav:cteyv'as\asd", True),
    ):
        action._create_new_layer()

    assert "nav:C" in mock_editor.config.layers
    assert "nav:C" in mock_editor.config.layer_order


def test_modifier_toggled_renames_layer():
    """Test that checking a modifier checkbox correctly renames an existing layer."""
    mock_editor = _create_mock_editor()
    mock_editor.config.layers["nav"] = {}
    mock_editor.config.layer_order.append("nav")

    action = ChangeLayerAction(mock_editor)

    # Simulate UI state
    action._layer_selector.clear()
    action._layer_selector.addItems(mock_editor.config.layer_order)
    action._layer_selector.setCurrentText("nav")

    # Act: Check 'A' (Alt) modifier
    action._mod_checkboxes["A"].setChecked(True)

    # Assert
    assert "nav:A" in mock_editor.config.layers
    assert "nav" not in mock_editor.config.layers
    assert "nav:A" in mock_editor.config.layer_order


def test_empty_programmatic_selection_does_not_create_layer_action():
    """Clearing the combo during a refresh must never write ``layer()``."""
    mock_editor = _create_mock_editor()
    key = MagicMock(spec=KeyItem)
    key.key_value = ""
    mock_editor.get_selected_key_item.return_value = key
    action = ChangeLayerAction(mock_editor)
    mock_editor.set_key_mapping.reset_mock()

    action._layer_selector.setCurrentIndex(-1)
    action._on_layer_selected("")

    mock_editor.set_key_mapping.assert_not_called()


def test_refreshing_layers_does_not_change_literal_mapping():
    """Rebuilding target-layer options is a read-only UI operation."""
    mock_editor = _create_mock_editor()
    key = MagicMock(spec=KeyItem)
    key.key_value = "right"
    mock_editor.get_selected_key_item.return_value = key
    action = ChangeLayerAction(mock_editor)
    mock_editor.set_key_mapping.reset_mock()

    action.on_layer_changed("main")

    mock_editor.set_key_mapping.assert_not_called()


def test_user_layer_selection_still_applies_mapping():
    """The signal guard must not block an actual user layer choice."""
    mock_editor = _create_mock_editor()
    mock_editor.config.layers["nav"] = {}
    mock_editor.config.layer_order.append("nav")
    key = MagicMock(spec=KeyItem)
    key.key_value = ""
    mock_editor.get_selected_key_item.return_value = key
    action = ChangeLayerAction(mock_editor)
    mock_editor.set_key_mapping.reset_mock()

    action._on_layer_selected("nav")

    mock_editor.set_key_mapping.assert_called_once_with(key, "layer(nav)")
