"""Tests for the ConfigEditor UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock, patch

from keyd.actions import ACTION_SPECS, ActionCategory
from keyd.config import Config
from keyd.layout import Layout
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from ui.config_editor import ConfigEditor
from ui.config_editor_bindings import LayerNameDialog
from ui.key_item import KeyItem
from ui.layout_editor import LayoutEditor


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


def test_config_source_and_visual_editor_synchronize_both_ways() -> None:
    """The side-panel source and keyboard view share one live model."""
    with (
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("live.conf")

    mock_scene = MagicMock()
    mock_view = MagicMock()
    key = KeyItem("a", "", QRectF(0, 0, 10, 10))
    mock_scene.items.return_value = [key]
    mock_scene.selectedItems.return_value = []

    editor = ConfigEditor(
        config=config,
        scene=mock_scene,
        view=mock_view,
    )

    editor.set_key_mapping(key, "b")
    assert "a = b" in editor.source_editor.toPlainText()

    editor.source_editor.setPlainText(
        """[ids]
1234:5678

[main]
a = right
"""
    )

    editor._run_keyd_validation()
    assert config.layers["main"]["a"] == "right"
    assert key.key_value == "right"
    assert "keyd syntax valid" in editor.source_status.text()
    assert "synchronized" not in editor.source_status.text()


def _create_live_editor_with_selected_key() -> tuple[ConfigEditor, Config, KeyItem]:
    """Create a real live-source editor and select one visual key after setup."""
    with (
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("selected-live.conf")

    mock_scene = MagicMock()
    mock_view = MagicMock()
    key = KeyItem("a", "", QRectF(0, 0, 10, 10))
    mock_scene.items.return_value = [key]
    mock_scene.selectedItems.return_value = []
    editor = ConfigEditor(config=config, scene=mock_scene, view=mock_view)
    mock_scene.selectedItems.return_value = [key]
    return editor, config, key


def _create_integrated_layout_editor() -> tuple[
    ConfigEditor, LayoutEditor, KeyItem
]:
    """Create the shared workspace with its reusable physical-layout controller."""
    with (
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("integrated.conf")

    mock_scene = MagicMock()
    mock_view = MagicMock()
    mock_view.mapToScene.return_value = QPointF(100, 100)
    key = KeyItem("a", "", QRectF(0, 0, 10, 10))
    mock_scene.items.return_value = [key]
    mock_scene.selectedItems.return_value = []
    with patch(
        "ui.layout_editor.load_layout",
        return_value=Layout(device_id="1234:5678"),
    ):
        layout_editor = LayoutEditor(
            device_id="1234:5678",
            scene=mock_scene,
            view=mock_view,
        )
    editor = ConfigEditor(
        config=config,
        scene=mock_scene,
        view=mock_view,
        layout_editor=layout_editor,
    )
    mock_scene.selectedItems.return_value = [key]
    return editor, layout_editor, key


def test_source_edit_does_not_replace_selected_literal_with_empty_layer():
    """Regression: any source keystroke used to turn the selected key into layer()."""
    editor, config, key = _create_live_editor_with_selected_key()

    editor.source_editor.setPlainText(
        """[ids]
1234:5678

[main]
a = right
"""
    )

    editor._run_keyd_validation()
    assert key.key_value == "right"
    assert config.layers["main"]["a"] == "right"
    assert "layer()" not in editor.source_editor.toPlainText()


def test_deleting_selected_binding_in_source_stays_deleted():
    """A deleted source binding must not be reintroduced by action widgets."""
    editor, config, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "left")

    editor.source_editor.setPlainText(
        """[ids]
1234:5678

[main]
"""
    )

    editor._run_keyd_validation()
    assert key.key_value == ""
    assert "a" not in config.layers["main"]
    assert "layer()" not in editor.source_editor.toPlainText()


def test_source_comment_keystroke_does_not_change_selected_mapping():
    """Editing only a comment is semantically read-only for visual mappings."""
    editor, config, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "C-a")

    editor.source_editor.setPlainText(
        """# personal note
[ids]
1234:5678

[main]
a = C-a
"""
    )

    assert key.key_value == "C-a"
    assert config.layers["main"]["a"] == "C-a"
    assert "layer()" not in editor.source_editor.toPlainText()


def test_valid_source_refresh_does_not_select_line_while_editing():
    """Validation must leave the manual source cursor safe for the next key."""
    editor, _, _ = _create_live_editor_with_selected_key()
    source = """[ids]
1234:5678

[main]
a = right
"""
    editor.source_editor.setPlainText(source)
    cursor = editor.source_editor.textCursor()
    position = source.index("right") + len("right")
    cursor.setPosition(position)
    editor.source_editor.setTextCursor(cursor)

    with patch(
        "ui.config_editor_source.Config.check_source_text",
        return_value=(True, "keyd syntax valid"),
    ):
        editor._run_keyd_validation()

    cursor = editor.source_editor.textCursor()
    assert cursor.hasSelection() is False
    assert cursor.position() == position

    editor.source_editor.insertPlainText("x")
    assert "a = rightx" in editor.source_editor.toPlainText()


def test_ctrl_s_formats_source_structure_and_preserves_cursor():
    """Ctrl+S formats spacing without turning the current line into a selection."""
    editor, _, _ = _create_live_editor_with_selected_key()
    source = """[ids]
1234:5678

[main]
a = left

b = right
[nav]
h = left
"""
    editor.source_editor.setPlainText(source)
    cursor = editor.source_editor.textCursor()
    position = source.index("b = right") + len("b =")
    cursor.setPosition(position)
    editor.source_editor.setTextCursor(cursor)

    QTest.keyClick(
        editor.source_editor,
        Qt.Key.Key_S,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert editor.source_editor.toPlainText() == """[ids]
1234:5678

[main]
a = left
b = right

[nav]
h = left
"""
    cursor = editor.source_editor.textCursor()
    assert cursor.block().text() == "b = right"
    assert cursor.positionInBlock() == len("b =")
    assert cursor.hasSelection() is False


def test_typing_comment_character_by_character_never_changes_selected_key():
    """Exercise the real per-keystroke textChanged path, including partial comments."""
    editor, config, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "overload(control, a)")
    cursor = editor.source_editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.source_editor.setTextCursor(cursor)

    for character in "\n# note":
        editor.source_editor.insertPlainText(character)
        assert key.key_value == "overload(control, a)"
        assert config.layers["main"]["a"] == "overload(control, a)"
        assert "layer()" not in editor.source_editor.toPlainText()


def test_reworked_layout_shows_binding_and_config_at_the_same_time():
    """Binding inspector and generated config are siblings, not exclusive tabs."""
    editor, _, _ = _create_live_editor_with_selected_key()
    editor._set_source_preview_visible(True, persist=False)

    assert editor.inspector_splitter.orientation() == Qt.Orientation.Vertical
    assert editor.actions_page.isHidden() is False
    assert editor.source_editor.isHidden() is False
    assert editor._splitter.indexOf(editor.layer_panel) == 0
    assert not hasattr(editor, "panel_tabs")


def test_config_editor_features_live_in_focused_modules():
    """The main editor remains an orchestrator instead of regaining all logic."""
    assert (
        ConfigEditor._sync_source_editor.__module__
        == "ui.config_editor_source"
    )
    assert (
        ConfigEditor._record_history.__module__
        == "ui.config_editor_history"
    )
    assert (
        ConfigEditor.enter_layout_mode.__module__
        == "ui.config_editor_layout"
    )
    assert (
        ConfigEditor.set_key_mapping.__module__
        == "ui.config_editor_bindings"
    )


def test_binding_uses_one_grouped_action_dropdown():
    """Literal input and every visual action share one grouped selector."""
    editor, _, _ = _create_live_editor_with_selected_key()

    assert editor._action_selector.itemText(0) == "Key / shortcut"
    assert editor._action_selector.itemData(0) == "literal"
    assert not hasattr(editor.keyd_action, "_action_selector")
    for category in ActionCategory:
        assert editor._action_selector.findText(category.value) >= 0
    for spec in ACTION_SPECS:
        assert (
            editor._action_selector.findData(spec.keyd_function) >= 0
        )


def test_editor_panels_have_no_artificial_resize_limits():
    """Both horizontal rails and the vertical inspector may be dragged freely."""
    editor, _, _ = _create_live_editor_with_selected_key()

    assert editor.layer_panel.minimumWidth() == 0
    assert editor.layer_panel.maximumWidth() == 16777215
    assert editor.side_panel.minimumWidth() == 0
    assert editor.side_panel.maximumWidth() == 16777215
    assert editor._splitter.childrenCollapsible() is True
    assert editor.inspector_splitter.childrenCollapsible() is True


def test_generated_config_is_always_editable_without_mode_button():
    """The source behaves like an editor without an Edit/Done mode switch."""
    editor, _, _ = _create_live_editor_with_selected_key()

    assert editor.source_editor.isReadOnly() is False
    assert not hasattr(editor, "edit_source_btn")
    original_source = editor.source_editor.toPlainText()
    cursor = editor.source_editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.source_editor.setTextCursor(cursor)
    QTest.keyClick(editor.source_editor, Qt.Key.Key_Tab)
    assert editor.source_editor.toPlainText() == original_source + "    "


def test_generated_config_can_be_collapsed_to_its_header():
    """Users who do not know text configs can hide the code without losing Binding."""
    editor, _, _ = _create_live_editor_with_selected_key()

    editor._set_source_preview_visible(False, persist=False)
    assert editor.source_editor.isHidden() is True
    assert editor.source_status.isHidden() is True
    assert editor.actions_page.isHidden() is False
    assert editor.toggle_source_btn.text() == "Show"

    editor._set_source_preview_visible(True, persist=False)
    assert editor.source_editor.isHidden() is False
    assert editor.toggle_source_btn.text() == "Hide"


def test_collapsed_config_restores_user_splitter_height():
    """Hide collapses to the header and Show restores the user's previous height."""
    editor, _, _ = _create_live_editor_with_selected_key()
    editor.resize(1200, 800)
    editor.show()
    editor._set_source_preview_visible(True, persist=False)
    editor.inspector_splitter.setSizes([190, 510])
    QApplication.processEvents()
    user_sizes = editor.inspector_splitter.sizes()

    editor._set_source_preview_visible(False, persist=False)
    QApplication.processEvents()
    collapsed_sizes = editor.inspector_splitter.sizes()

    assert collapsed_sizes[1] < user_sizes[1]
    assert editor._source_splitter_sizes == user_sizes

    editor._set_source_preview_visible(True, persist=False)
    QApplication.processEvents()
    restored_sizes = editor.inspector_splitter.sizes()

    assert abs(restored_sizes[0] - user_sizes[0]) <= 2
    assert abs(restored_sizes[1] - user_sizes[1]) <= 2
    editor.hide()


def test_expand_generated_config_can_restore_binding_inspector():
    """Full config editing is temporary and restores the simultaneous layout."""
    editor, _, _ = _create_live_editor_with_selected_key()

    editor.expand_source_btn.setChecked(True)
    assert editor.actions_page.isHidden() is True
    assert editor.expand_source_btn.text() == "Restore"

    editor.expand_source_btn.setChecked(False)
    assert editor.actions_page.isHidden() is False
    assert editor.expand_source_btn.text() == "Expand"


def test_invalid_source_keeps_last_valid_visual_state():
    """Partial source syntax must not clear or corrupt the keyboard visualization."""
    editor, config, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "left")

    editor.source_editor.setPlainText("[main]\na = right\n")

    assert key.key_value == "left"
    assert config.layers["main"]["a"] == "left"
    assert editor.save_apply_btn.isEnabled() is False
    assert "first section must be [ids]" in editor.source_status.text()


def test_keyd_rejected_source_keeps_last_valid_visual_state():
    """Semantic errors found by keyd must not leak into the keyboard model."""
    editor, config, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "left")

    editor.source_editor.setPlainText(
        """[ids]
1234:5678

[main]
a = layer(
"""
    )
    editor._run_keyd_validation()

    assert key.key_value == "left"
    assert config.layers["main"]["a"] == "left"
    assert editor.save_apply_btn.isEnabled() is False
    assert "keyd syntax valid" not in editor.source_status.text()


def test_save_flushes_pending_valid_source_edit():
    """Saving persists the current draft without closing the editor."""
    editor, config, key = _create_live_editor_with_selected_key()
    config.save = MagicMock()
    close_requested = MagicMock()
    editor.cancel_requested.connect(close_requested)
    editor.source_editor.setPlainText(
        """[ids]
1234:5678

[main]
a = right
"""
    )

    editor._save()

    assert config.layers["main"]["a"] == "right"
    assert key.key_value == "right"
    config.save.assert_called_once()
    close_requested.assert_not_called()


def test_back_button_names_its_destination() -> None:
    """Top-left navigation communicates where it takes the user."""
    editor, _, _ = _create_live_editor_with_selected_key()

    assert editor.back_btn.text() == "← Configurations"
    assert editor.back_btn.toolTip() == "Return to the configuration list"


def test_visual_change_uses_shared_undo_and_redo_history():
    """Top-bar history spans generated source and the visual keyboard model."""
    editor, config, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "left")
    assert editor.overall_status.text() == "Unsaved changes"
    assert editor.undo_btn.isEnabled() is True

    editor.undo_config_change()
    assert key.key_value == ""
    assert "a" not in config.layers["main"]

    editor.redo_config_change()
    assert key.key_value == "left"
    assert config.layers["main"]["a"] == "left"


def test_visual_binding_change_reveals_line_without_selecting_it():
    """Visual changes may navigate source but cannot arm it for replacement."""
    editor, _, key = _create_live_editor_with_selected_key()

    editor.set_key_mapping(key, "layer(nav)")

    cursor = editor.source_editor.textCursor()
    assert cursor.block().text() == "a = layer(nav)"
    assert cursor.hasSelection() is False


def test_keyd_action_is_loaded_as_normalized_visual_form():
    """Internal macro variants appear as an option on their base action."""
    editor, _, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "layerm(nav, macro(C-a))")

    editor._on_selection_changed()

    assert editor._action_selector.currentText() == "Hold layer"
    assert editor.keyd_action.current_action_name == "layer"
    assert editor.keyd_action._macro_checkbox.isChecked() is True
    assert editor.keyd_action._macro_input.text() == "macro(C-a)"


def test_visual_keyd_action_immediately_updates_generated_config():
    """A complete visual action writes its low-level syntax to the live preview."""
    editor, config, key = _create_live_editor_with_selected_key()
    config.add_layer("nav")
    editor.on_config_structure_changed()
    editor._action_selector.setCurrentIndex(
        editor._action_selector.findData("toggle")
    )
    action = editor.keyd_action
    action._field_widgets["layer"].setCurrentText("nav")
    action._macro_checkbox.setChecked(True)
    action._macro_input.setText("macro(C-a)")

    action._apply()

    assert key.key_value == "togglem(nav, macro(C-a))"
    assert "a = togglem(nav, macro(C-a))" in editor.source_editor.toPlainText()


def test_single_dropdown_can_switch_between_structured_actions():
    """Choosing a new incomplete form must keep the old binding until completed."""
    editor, _, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "toggle(nav)")
    editor._on_selection_changed()

    editor._action_selector.setCurrentIndex(
        editor._action_selector.findData("overload")
    )

    assert editor.keyd_action.isEnabled() is True
    assert editor.keyd_action.current_action_name == "overload"
    assert key.key_value == "toggle(nav)"
    assert set(editor.keyd_action._field_widgets) == {"layer", "action"}


def test_layer_rail_changes_the_active_visual_layer():
    """The left rail replaces the old toolbar combobox as visible navigation."""
    editor, config, key = _create_live_editor_with_selected_key()
    config.add_layer("nav")
    config.set_mapping("nav", "a", "down")
    editor.on_config_structure_changed()

    nav_item = editor.layer_list.findItems("nav", Qt.MatchFlag.MatchExactly)[0]
    editor.layer_list.setCurrentItem(nav_item)

    assert editor._current_layer == "nav"
    assert key.key_value == "down"


def test_layer_change_scrolls_generated_config_to_layer_declaration():
    """Changing the active layer reveals its declaration in generated source."""
    editor, config, _ = _create_live_editor_with_selected_key()
    config.add_layer("nav")
    config.set_mapping("nav", "h", "left")
    editor.on_config_structure_changed()

    nav_item = editor.layer_list.findItems("nav", Qt.MatchFlag.MatchExactly)[0]
    editor.layer_list.setCurrentItem(nav_item)

    cursor = editor.source_editor.textCursor()
    assert cursor.block().text() == "[nav]"
    assert editor.source_editor.verticalScrollBar().value() == cursor.blockNumber()


def test_selecting_mapped_key_scrolls_to_binding_in_active_layer():
    """A mapped key reveals the exact binding line, not only the section."""
    editor, _, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "right")
    editor.source_editor.scroll_line_to_top = MagicMock()
    editor.source_editor.ensureCursorVisible = MagicMock()

    editor._on_selection_changed()

    cursor = editor.source_editor.textCursor()
    assert cursor.block().text() == "a = right"
    assert cursor.hasSelection() is False
    editor.source_editor.ensureCursorVisible.assert_called()
    editor.source_editor.scroll_line_to_top.assert_not_called()


def test_selecting_unmapped_key_scrolls_to_active_layer_declaration():
    """Without a binding, key selection falls back to the active layer header."""
    editor, _, _ = _create_live_editor_with_selected_key()
    editor.source_editor.scroll_line_to_top = MagicMock()
    editor.source_editor.ensureCursorVisible = MagicMock()

    editor._on_selection_changed()

    cursor = editor.source_editor.textCursor()
    assert cursor.block().text() == "[main]"
    assert cursor.hasSelection() is False
    editor.source_editor.ensureCursorVisible.assert_called()
    editor.source_editor.scroll_line_to_top.assert_not_called()


def test_layer_rail_creation_does_not_remap_selected_key():
    """The navigation rail's + Layer action is not a Change Layer binding action."""
    editor, config, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "left")

    with patch(
        "ui.config_editor_bindings.LayerNameDialog.get_name",
        return_value=("nav:C", True),
    ):
        editor._create_new_layer()

    assert "nav:C" in config.layers
    assert config.layers["main"]["a"] == "left"
    assert "layer(nav)" not in config.source()


def test_new_layer_dialog_composes_exactly_one_modifier():
    """Choosing a modifier updates the preview and replaces the prior choice."""
    dialog = LayerNameDialog()
    dialog.name_edit.setText("navigation")

    dialog.modifier_buttons["A"].click()

    assert dialog.layer_name() == "navigation:A"
    assert dialog.preview_label.text() == "Result: navigation:A"
    assert dialog.modifier_buttons["A"].isChecked() is True

    dialog.modifier_buttons["C"].click()

    assert dialog.layer_name() == "navigation:C"
    assert dialog.modifier_buttons["A"].isChecked() is False
    assert dialog.modifier_buttons["C"].isChecked() is True
    assert dialog.dialog_buttons.button(
        QDialogButtonBox.StandardButton.Ok
    ).isEnabled()


def test_f2_renames_focused_sidebar_layer_and_keeps_selection():
    """F2 in the layer rail renames the model, source, and current layer."""
    editor, config, _ = _create_live_editor_with_selected_key()
    config.add_layer("nav")
    config.set_mapping("main", "capslock", "layer(nav)")
    editor.on_config_structure_changed()
    nav_item = editor.layer_list.findItems("nav", Qt.MatchFlag.MatchExactly)[0]
    editor.layer_list.setCurrentItem(nav_item)
    editor.layer_list.setFocus()

    with patch(
        "ui.config_editor_bindings.QInputDialog.getText",
        return_value=("movement", True),
    ):
        QTest.keyClick(editor.layer_list, Qt.Key.Key_F2)
        QApplication.processEvents()

    assert editor._current_layer == "movement"
    assert "movement" in config.layers
    assert "nav" not in config.layers
    assert "[movement]" in editor.source_editor.toPlainText()
    assert "layer(movement)" in editor.source_editor.toPlainText()
    assert editor.layer_list.currentItem().text() == "movement"


def test_main_layer_cannot_be_renamed_from_sidebar():
    """The mandatory main layer ignores the rename command."""
    editor, config, _ = _create_live_editor_with_selected_key()

    with patch(
        "ui.config_editor_bindings.QInputDialog.getText"
    ) as rename_dialog:
        editor._rename_current_layer()

    rename_dialog.assert_not_called()
    assert config.layer_order == ["main"]


def test_physical_layout_uses_same_workspace_and_integrated_inspector():
    """Physical layout mode replaces inspector content without opening another page."""
    editor, _, key = _create_integrated_layout_editor()
    editor.activate_mode()
    assert key.locked is True

    editor.enter_layout_mode()

    assert editor._editing_layout is True
    assert editor.inspector_stack.currentWidget() == editor.layout_inspector
    assert editor.layer_list.isEnabled() is False
    assert editor.save_apply_btn.text() == "Save layout and Done"
    assert key.locked is False


def test_saving_integrated_layout_returns_to_last_layer():
    """Save layout and Done persists geometry and restores Binding/config."""
    editor, layout_editor, key = _create_integrated_layout_editor()
    layout_editor.save_current_layout = MagicMock()
    editor.enter_layout_mode()

    editor._save()

    layout_editor.save_current_layout.assert_called_once()
    assert editor._editing_layout is False
    assert editor.inspector_stack.currentWidget() == editor.inspector_splitter
    assert editor.save_apply_btn.text() == "Save and Apply"
    assert editor.layer_list.isEnabled() is True
    assert key.locked is True


def test_clicking_physical_layout_again_saves_and_exits_mode():
    """The left navigation item behaves as a friendly two-way mode toggle."""
    editor, layout_editor, _ = _create_integrated_layout_editor()
    layout_editor.save_current_layout = MagicMock()

    editor.keyboard_layout_btn.click()
    assert editor._editing_layout is True
    assert editor.keyboard_layout_btn.isChecked() is True

    editor.keyboard_layout_btn.click()

    layout_editor.save_current_layout.assert_called_once()
    assert editor._editing_layout is False
    assert editor.keyboard_layout_btn.isChecked() is False
    assert editor.inspector_stack.currentWidget() == editor.inspector_splitter


def test_back_from_layout_discards_geometry_without_leaving_config():
    """Back in layout mode reloads saved geometry and stays in the editor shell."""
    editor, layout_editor, _ = _create_integrated_layout_editor()
    layout_editor.reload_saved_layout = MagicMock()
    close_requested = MagicMock()
    editor.cancel_requested.connect(close_requested)
    editor.enter_layout_mode()

    editor._handle_back()

    layout_editor.reload_saved_layout.assert_called_once()
    close_requested.assert_not_called()
    assert editor._editing_layout is False


def test_integrated_key_inspector_renames_selected_physical_key():
    """The right Key inspector reuses LayoutEditor's validation/controller."""
    editor, _, key = _create_integrated_layout_editor()
    editor.enter_layout_mode()
    editor._update_layout_selection()

    editor._apply_layout_key_name("enter")

    assert key.key_name == "enter"
    assert editor.layout_name_input.styleSheet() == ""
