"""Tests for the unified binding and physical-layout workspace."""
# pylint: disable=protected-access

from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from ui.combined_editor import CombinedEditor


@patch("ui.combined_editor.does_layout_exist", return_value=True)
def test_combined_editor_has_no_layout_config_tabs(_mock_layout_exists) -> None:
    """The user edits both concerns in one persistent ConfigEditor shell."""
    editor = CombinedEditor("__combined_test__.conf", "1234:5678")

    assert not hasattr(editor, "tabs")
    assert editor.layout().indexOf(editor.config_editor) == 0
    assert editor.config_editor._layout_editor is editor.layout_editor


@patch("ui.combined_editor.does_layout_exist", return_value=True)
def test_layout_controller_remains_invisible_when_workspace_is_shown(
    _mock_layout_exists,
) -> None:
    """The reusable LayoutEditor must not appear behind the integrated UI."""
    editor = CombinedEditor("__combined_hidden_layout__.conf", "1234:5678")

    editor.show()
    QApplication.processEvents()

    assert editor.layout_editor.isVisible() is False
    editor.close()


@patch("ui.combined_editor.does_layout_exist", return_value=False)
def test_missing_layout_opens_integrated_physical_layout(_mock_layout_exists) -> None:
    """First-run layout creation no longer navigates to a separate application page."""
    editor = CombinedEditor("__combined_new__.conf", "1234:5678")

    assert editor.config_editor._editing_layout is True
    assert (
        editor.config_editor.inspector_stack.currentWidget()
        == editor.config_editor.layout_inspector
    )


@patch("ui.combined_editor.does_layout_exist", return_value=True)
def test_shutdown_detaches_editors_before_shared_scene_is_deleted(
    _mock_layout_exists,
) -> None:
    """Closing cannot deliver selection callbacks into a deleted C++ scene."""
    editor = CombinedEditor("__combined_shutdown__.conf", "1234:5678")
    scene = editor.shared_scene

    editor.shutdown()
    scene.deleteLater()
    QApplication.processEvents()

    assert editor.config_editor._context_attached is False
    assert editor.layout_editor._context_attached is False
    assert editor.shared_view.scene() is None
    # A callback already queued before shutdown is harmless as well.
    editor.layout_editor._on_selection_changed()
