"""Tests for the unified visual keyd action editor."""

# pylint: disable=protected-access

from unittest.mock import MagicMock

from PySide6.QtWidgets import QComboBox, QLineEdit, QSpinBox
from ui.actions.keyd_action import KeydActionEditor
from ui.key_item import KeyItem


def _create_action(value: str = "") -> tuple[KeydActionEditor, MagicMock, MagicMock]:
    editor = MagicMock()
    editor.config.layer_order = ["main", "nav", "shift:C"]
    key = MagicMock(spec=KeyItem)
    key.key_value = value
    editor.get_selected_key_item.return_value = key
    action = KeydActionEditor(editor)
    action.on_selection_changed(key)
    editor.set_key_mapping.reset_mock()
    return action, editor, key


def _select_action(action: KeydActionEditor, action_id: str) -> None:
    index = action._action_selector.findData(action_id)
    assert index >= 0
    action._action_selector.setCurrentIndex(index)


def _set_field(action: KeydActionEditor, name: str, value: str) -> None:
    widget = action._field_widgets[name]
    if isinstance(widget, QSpinBox):
        widget.setValue(int(value))
    elif isinstance(widget, QComboBox):
        widget.setCurrentText(value)
    elif isinstance(widget, QLineEdit):
        widget.setText(value)
    else:
        raise AssertionError(f"Unsupported test widget: {type(widget)}")


def test_layer_action_can_run_macro_without_exposing_layerm():
    """The form keeps one layer action and generates its internal variant."""
    action, editor, key = _create_action()
    _select_action(action, "layer")
    _set_field(action, "layer", "nav")
    action._macro_checkbox.setChecked(True)
    action._macro_input.setText("macro(C-a C-c)")

    action._apply()

    editor.set_key_mapping.assert_called_with(
        key, "layerm(nav, macro(C-a C-c))"
    )
    assert action._action_selector.findData("layerm") == -1


def test_oneshot_additional_behaviours_are_mutually_exclusive():
    """One-shot can use ``oneshotm`` or ``oneshotk`` through one clean form."""
    action, editor, key = _create_action()
    _select_action(action, "oneshot")
    _set_field(action, "layer", "nav")
    action._macro_checkbox.setChecked(True)
    action._macro_input.setText("macro(a)")
    action._held_key_checkbox.setChecked(True)
    action._held_key_input.setText("a")

    action._apply()

    assert action._macro_checkbox.isChecked() is False
    editor.set_key_mapping.assert_called_with(
        key, "oneshotk(nav, a)"
    )


def test_existing_macro_variant_loads_as_base_action_and_option():
    """Manual low-level syntax round-trips to the normalized visual controls."""
    action, _, _ = _create_action("swapm(nav, macro(C-left))")

    assert action.current_action_name == "swap"
    assert action._field_widgets["layer"].currentText() == "nav"
    assert action._macro_checkbox.isChecked() is True
    assert action._macro_input.text() == "macro(C-left)"


def test_existing_nested_action_populates_each_documented_field():
    """Nested calls and timeouts remain editable after parsing source text."""
    action, _, _ = _create_action(
        "timeout(layer(nav), 250, macro(C-a C-c))"
    )

    assert action.current_action_name == "timeout"
    assert action._field_widgets["action"].text() == "layer(nav)"
    assert action._field_widgets["timeout"].value() == 250
    assert (
        action._field_widgets["second_action"].text()
        == "macro(C-a C-c)"
    )


def test_incomplete_action_form_does_not_overwrite_binding():
    """Choosing an action waits for every required argument."""
    action, editor, _ = _create_action("right")

    _select_action(action, "overload")

    editor.set_key_mapping.assert_not_called()


def test_zero_argument_action_applies_immediately():
    """Actions such as clear and repeat need no artificial confirmation step."""
    action, editor, key = _create_action()

    _select_action(action, "repeat")

    editor.set_key_mapping.assert_called_with(key, "repeat()")


def test_layer_options_use_base_names_and_allow_custom_layout_names():
    """Modified section names do not leak into layer action arguments."""
    action, _, _ = _create_action()
    _select_action(action, "setlayout")
    widget = action._field_widgets["layout"]

    assert widget.findText("shift") >= 0
    assert widget.findText("shift:C") == -1
    assert widget.isEditable() is True
