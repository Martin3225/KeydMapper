"""Tests for the unified binding and physical-layout workspace."""
# pylint: disable=protected-access

from unittest.mock import patch

from ui.combined_editor import CombinedEditor


@patch("ui.combined_editor.does_layout_exist", return_value=True)
def test_combined_editor_has_no_layout_config_tabs(_mock_layout_exists) -> None:
    """The user edits both concerns in one persistent ConfigEditor shell."""
    editor = CombinedEditor("__combined_test__.conf", "1234:5678")

    assert not hasattr(editor, "tabs")
    assert editor.layout().indexOf(editor.config_editor) == 0
    assert editor.config_editor._layout_editor is editor.layout_editor


@patch("ui.combined_editor.does_layout_exist", return_value=False)
def test_missing_layout_opens_integrated_physical_layout(_mock_layout_exists) -> None:
    """First-run layout creation no longer navigates to a separate application page."""
    editor = CombinedEditor("__combined_new__.conf", "1234:5678")

    assert editor.config_editor._editing_layout is True
    assert (
        editor.config_editor.inspector_stack.currentWidget()
        == editor.config_editor.layout_inspector
    )
