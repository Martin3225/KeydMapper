"""Tests for the ConfigEditor UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock, patch

from keyd.config import Config
from PySide6.QtCore import QRectF
from PySide6.QtGui import QTextCursor
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

    assert config.layers["main"]["a"] == "right"
    assert key.key_value == "right"
    assert "synchronized" in editor.source_status.text()


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
