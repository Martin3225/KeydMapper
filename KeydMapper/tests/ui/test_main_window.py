"""Tests for application-wide main-window behavior."""
# pylint: disable=protected-access

from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


@patch("ui.config_selector.os.listdir", return_value=[])
def test_ctrl_q_action_closes_main_window(_mock_listdir) -> None:
    """The app-wide Ctrl+Q action closes the main window."""
    window = MainWindow()
    window.show()
    window.activateWindow()
    window._selector_page.new_config_btn.setFocus()
    QApplication.processEvents()

    assert window._quit_action.shortcut() == QKeySequence("Ctrl+Q")
    assert (
        window._quit_action.shortcutContext()
        == Qt.ShortcutContext.ApplicationShortcut
    )

    QTest.keyClick(
        window._selector_page.new_config_btn,
        Qt.Key.Key_Q,
        Qt.KeyboardModifier.ControlModifier,
    )
    QApplication.processEvents()

    assert window.isVisible() is False


@patch("ui.config_selector.os.listdir", return_value=[])
def test_application_shortcuts_create_config_and_show_help(_mock_listdir) -> None:
    """Ctrl+N and both help gestures are registered application-wide."""
    window = MainWindow()
    new_action = window._application_actions["new_config"]
    help_action = window._application_actions["shortcuts"]

    assert new_action.shortcuts() == [QKeySequence("Ctrl+N")]
    assert help_action.shortcuts() == [
        QKeySequence("F1"),
        QKeySequence("Ctrl+?"),
    ]

    with patch.object(
        window._selector_page, "create_new_config"
    ) as create_mock:
        new_action.trigger()
        create_mock.assert_called_once()

    with patch("ui.main_window.QMessageBox.information") as information:
        help_action.trigger()
    assert "Ctrl+S" in information.call_args.args[2]
    assert "Ctrl+A" in information.call_args.args[2]
