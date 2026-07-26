"""Tests for the ConfigEditor UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock, patch

from keyd.config import Config
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
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


def test_editor_panels_have_no_artificial_resize_limits():
    """Both horizontal rails and the vertical inspector may be dragged freely."""
    editor, _, _ = _create_live_editor_with_selected_key()

    assert editor.layer_panel.minimumWidth() == 0
    assert editor.layer_panel.maximumWidth() == 16777215
    assert editor.side_panel.minimumWidth() == 0
    assert editor.side_panel.maximumWidth() == 16777215
    assert editor._splitter.childrenCollapsible() is True
    assert editor.inspector_splitter.childrenCollapsible() is True


def test_generated_config_is_read_only_until_edit_is_requested():
    """Manual config editing must be an explicit action."""
    editor, _, _ = _create_live_editor_with_selected_key()

    assert editor.source_editor.isReadOnly() is True
    original_source = editor.source_editor.toPlainText()
    QTest.keyClick(editor.source_editor, Qt.Key.Key_Tab)
    assert editor.source_editor.toPlainText() == original_source

    editor.edit_source_btn.setChecked(True)
    assert editor.source_editor.isReadOnly() is False
    assert editor.edit_source_btn.text() == "Done editing"

    editor.edit_source_btn.setChecked(False)
    assert editor.source_editor.isReadOnly() is True
    assert editor.edit_source_btn.text() == "Edit config"


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
    """Saving immediately after typing must persist the draft, not the old model."""
    editor, config, key = _create_live_editor_with_selected_key()
    config.save = MagicMock()
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


def test_visual_binding_change_reveals_generated_config_line():
    """The preview immediately shows which line a Binding change generated."""
    editor, _, key = _create_live_editor_with_selected_key()

    editor.set_key_mapping(key, "layer(nav)")

    assert "a = layer(nav)" in editor.source_editor.textCursor().selectedText()


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

    assert editor.source_editor.textCursor().block().text() == "[nav]"


def test_selecting_mapped_key_scrolls_to_binding_in_active_layer():
    """A mapped key reveals the exact binding line, not only the section."""
    editor, _, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "right")

    editor._on_selection_changed()

    assert editor.source_editor.textCursor().selectedText() == "a = right"


def test_selecting_unmapped_key_scrolls_to_active_layer_declaration():
    """Without a binding, key selection falls back to the active layer header."""
    editor, _, _ = _create_live_editor_with_selected_key()

    editor._on_selection_changed()

    cursor = editor.source_editor.textCursor()
    assert cursor.block().text() == "[main]"
    assert cursor.hasSelection() is False


def test_layer_rail_creation_does_not_remap_selected_key():
    """The navigation rail's + Layer action is not a Change Layer binding action."""
    editor, config, key = _create_live_editor_with_selected_key()
    editor.set_key_mapping(key, "left")

    with patch(
        "ui.config_editor.QInputDialog.getText",
        return_value=("nav:C", True),
    ):
        editor._create_new_layer()

    assert "nav:C" in config.layers
    assert config.layers["main"]["a"] == "left"
    assert "layer(nav)" not in config.source()
