"""Tests for the SetValueAction UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock

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
