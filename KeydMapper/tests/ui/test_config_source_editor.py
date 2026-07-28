"""Tests for source-editor keyboard and focus interactions."""
# pylint: disable=protected-access

from unittest.mock import MagicMock

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFocusEvent, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from ui.config_source_editor import KeydSourceEditor


def test_alt_arrows_move_current_line_and_keep_cursor() -> None:
    """Alt+Up/Down moves a line instead of editing its contents."""
    editor = KeydSourceEditor()
    editor.setPlainText("first\nsecond\nthird\n")
    cursor = QTextCursor(editor.document().findBlockByNumber(1))
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
    editor.setTextCursor(cursor)

    QTest.keyClick(
        editor,
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.AltModifier,
    )

    assert editor.toPlainText() == "second\nfirst\nthird\n"
    assert editor.textCursor().block().text() == "second"
    assert editor.textCursor().positionInBlock() == len("second")

    QTest.keyClick(
        editor,
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.AltModifier,
    )
    assert editor.toPlainText() == "first\nsecond\nthird\n"


def test_alt_arrow_moves_selected_line_block_together() -> None:
    """A multi-line selection remains selected after moving as one block."""
    editor = KeydSourceEditor()
    editor.setPlainText("one\ntwo\nthree\nfour")
    cursor = QTextCursor(editor.document().findBlockByNumber(1))
    cursor.setPosition(
        editor.document().findBlockByNumber(2).position() + len("three"),
        QTextCursor.MoveMode.KeepAnchor,
    )
    editor.setTextCursor(cursor)

    QTest.keyClick(
        editor,
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.AltModifier,
    )

    assert editor.toPlainText() == "one\nfour\ntwo\nthree"
    assert editor.textCursor().selectedText() == "two\u2029three"


def test_ctrl_s_and_real_focus_out_request_formatting() -> None:
    """Both explicit save gesture and leaving the editor request formatting."""
    editor = KeydSourceEditor()
    requested = MagicMock()
    editor.format_requested.connect(requested)

    QTest.keyClick(
        editor,
        Qt.Key.Key_S,
        Qt.KeyboardModifier.ControlModifier,
    )
    focus_out = QFocusEvent(
        QEvent.Type.FocusOut,
        Qt.FocusReason.MouseFocusReason,
    )
    QApplication.sendEvent(editor, focus_out)

    assert requested.call_count == 2


def test_completion_popup_focus_does_not_request_formatting() -> None:
    """Opening completion cannot reformat the document under its popup."""
    editor = KeydSourceEditor()
    requested = MagicMock()
    editor.format_requested.connect(requested)
    popup_focus = QFocusEvent(
        QEvent.Type.FocusOut,
        Qt.FocusReason.PopupFocusReason,
    )

    QApplication.sendEvent(editor, popup_focus)

    requested.assert_not_called()
