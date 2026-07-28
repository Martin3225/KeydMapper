"""Tests for the SetValueAction UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication
from ui.actions.set_value import SetValueAction
from ui.key_item import KeyItem


def test_set_value_action_checkboxes_update_text():
    """Test that clicking modifier checkboxes updates the input text field."""
    # Arrange
    mock_editor = MagicMock()
    action = SetValueAction(mock_editor)

    # Act
    action._mod_checkboxes["C"].setChecked(True)
    action._mod_checkboxes["S"].setChecked(True)

    # Assert
    assert action._value_input.text() == "C-S-"

    # Act
    action._value_input.setText("C-S-a")
    action._mod_checkboxes["C"].setChecked(False)

    # Assert
    assert action._value_input.text() == "S-a"


def test_set_value_action_text_updates_checkboxes():
    """Test that manually typing text correctly updates the modifier checkboxes."""
    # Arrange
    mock_editor = MagicMock()

    key = MagicMock(spec=KeyItem)
    key.key_name = "x"
    mock_editor.get_selected_key_item.return_value = key

    action = SetValueAction(mock_editor)

    # Act
    action._value_input.setText("M-A-delete")
    action._apply_key_value()

    # Assert
    assert action._mod_checkboxes["M"].isChecked() is True
    assert action._mod_checkboxes["A"].isChecked() is True
    assert action._mod_checkboxes["C"].isChecked() is False
    assert action._mod_checkboxes["S"].isChecked() is False


def test_set_value_action_validation_styling():
    """Test that the input field applies orange styling on invalid input."""
    # Arrange
    mock_editor = MagicMock()

    key = MagicMock(spec=KeyItem)
    mock_editor.get_selected_key_item.return_value = key

    action = SetValueAction(mock_editor)

    # Act - Invalid input
    action._value_input.setText("X-chalupa")
    action._apply_key_value()

    # Assert
    assert "border: 2px solid orange;" in action._value_input.styleSheet()

    # Act - Valid input
    action._value_input.setText("C-delete")
    action._apply_key_value()

    # Assert
    assert action._value_input.styleSheet() == ""


def test_binding_key_completion_preserves_typed_modifiers() -> None:
    """Suggestions complete the base key rather than replacing C-S-."""
    mock_editor = MagicMock()
    mock_editor.config.device_id = "1234:5678"
    with patch(
        "ui.actions.set_value.get_valid_keys",
        return_value=frozenset({"delete", "down", "enter"}),
    ):
        action = SetValueAction(mock_editor)

    action._value_input.setText("C-S-del")
    completer = action._key_completer
    delete_index = completer.model().index(0, 0)

    assert completer.splitPath("C-S-del") == ["del"]
    assert completer.pathFromIndex(delete_index) == "C-S-delete"
    assert action._value_input.completer() is completer


def test_binding_completion_revalidates_and_updates_model() -> None:
    """Accepting a suggestion cannot leave the partial value applied internally."""
    mock_editor = MagicMock()
    mock_editor.config.device_id = "1234:5678"
    key = MagicMock(spec=KeyItem)
    mock_editor.get_selected_key_item.return_value = key
    action = SetValueAction(mock_editor)

    with patch(
        "ui.actions.set_value.is_valid_value",
        side_effect=lambda value: value == "delete",
    ):
        action._value_input.setText("del")
        action._apply_key_value()
        assert "orange" in action._value_input.styleSheet()
        mock_editor.set_key_mapping.reset_mock()

        # QLineEdit inserts the accepted completion without textEdited.
        action._value_input.setText("delete")
        action._key_completer.activated.emit("delete")
        QApplication.processEvents()

    assert action._value_input.styleSheet() == ""
    mock_editor.set_key_mapping.assert_called_once_with(key, "delete")


def test_set_value_recording_uses_physical_keyd_monitor():
    """The Binding recorder applies the helper's physical shortcut result."""
    mock_editor = MagicMock()
    mock_editor.config.device_id = "1234:5678"
    key = MagicMock(spec=KeyItem)
    mock_editor.get_selected_key_item.return_value = key
    action = SetValueAction(mock_editor)

    action._recorder.key_recorded.emit("C-a")

    assert action._value_input.text() == "C-a"
    mock_editor.set_key_mapping.assert_called_with(key, "C-a")
    assert action._recorder._device_id == "1234:5678"
    assert action._recorder._capture_shortcut is True
