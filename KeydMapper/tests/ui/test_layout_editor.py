"""Tests for the LayoutEditor UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock, patch

from PySide6.QtCore import QPointF, QRectF
from ui.key_item import KEY_DEFAULT_HEIGHT, KEY_DEFAULT_WIDTH, KeyItem
from ui.layout_editor import LayoutEditor


def test_layout_editor_add_button():
    """Test that adding a button places it in the scene."""

    # Arrange
    mock_scene = MagicMock()
    mock_view = MagicMock()

    mock_view.mapToScene.return_value = QPointF(100, 100)

    editor = LayoutEditor(
        device_id="test_device",
        scene=mock_scene,
        view=mock_view,
    )

    # Reset mock after initialization
    mock_scene.addItem.reset_mock()

    # Act
    editor._add_button()

    # Assert
    mock_scene.addItem.assert_called_once()
    added_item = mock_scene.addItem.call_args[0][0]
    assert isinstance(added_item, KeyItem)
    assert added_item.x() == 100 - KEY_DEFAULT_WIDTH / 2
    assert added_item.y() == 100 - KEY_DEFAULT_HEIGHT / 2


def test_layout_editor_delete_key():
    """Test that deleting a key removes it from the scene."""

    # Arrange
    mock_scene = MagicMock()
    mock_view = MagicMock()

    editor = LayoutEditor(
        device_id="test_device",
        scene=mock_scene,
        view=mock_view,
    )

    item1 = MagicMock(spec=KeyItem)
    item2 = MagicMock()
    mock_scene.selectedItems.return_value = [item1, item2]

    # Act
    editor._delete_key()

    # Verify only the KeyItem is removed
    mock_scene.removeItem.assert_called_once_with(item1)


@patch("keyd.key_validator.get_valid_keys")
def test_layout_editor_apply_invalid_key(mock_get_valid_keys) -> None:
    """Test that applying an invalid key name adds visual feedback (red/orange border)."""
    mock_get_valid_keys.return_value = frozenset(
        ["enter", "esc", "a"]
    )  # for windows, and missing keyd runs

    # Arrange
    mock_scene = MagicMock()
    mock_view = MagicMock()

    editor = LayoutEditor(
        device_id="test_device",
        scene=mock_scene,
        view=mock_view,
    )

    key = KeyItem("a", "", QRectF(0, 0, 10, 10))
    editor.get_selected_key_item = MagicMock(return_value=key)

    # Act
    editor._name_input.setText("enter")
    editor._apply_key()

    # Assert
    assert editor._name_input.styleSheet() == ""
    assert key.key_name == "enter"

    # Act 2 - invalid key name
    editor._name_input.setText("chrabryTrakturek")
    editor._apply_key()

    # Assert 2
    assert "orange" in editor._name_input.styleSheet()
    assert key.key_name == "enter"  # unchanged

    # Arrange - duplicate key name
    key2 = KeyItem("esc", "", QRectF(20, 20, 10, 10))
    mock_scene.items.return_value = [key, key2]

    # Act 3 - duplicate key name
    editor._name_input.setText("esc")
    editor._apply_key()

    # Assert 3
    assert "red" in editor._name_input.styleSheet()
    assert key.key_name == "enter"  # unchanged


def test_layout_editor_copy_paste() -> None:
    """Test that copying and pasting keys replicates them properly."""
    # Arrange
    mock_scene = MagicMock()
    mock_view = MagicMock()
    mock_view.mapToScene.return_value = QPointF(200, 200)

    editor = LayoutEditor(
        device_id="test_device",
        scene=mock_scene,
        view=mock_view,
    )

    key = KeyItem("Key", "", QRectF(10, 10, 50, 50))
    key.setPos(10, 10)
    mock_scene.selectedItems.return_value = [key]

    # Act
    editor._copy_keys()

    assert len(editor._clipboard) == 1

    mock_scene.addItem.reset_mock()
    editor._paste_keys()

    # Assert
    mock_scene.addItem.assert_called_once()
    added_item = mock_scene.addItem.call_args[0][0]
    assert isinstance(added_item, KeyItem)
