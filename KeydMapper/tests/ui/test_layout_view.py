"""Tests for keyboard commands handled by the physical-layout canvas."""

from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from ui.layout_view import LayoutView


def test_ctrl_a_selects_all_and_insert_adds_key() -> None:
    """Conventional selection replaces Ctrl+A's former add-key behavior."""
    view = LayoutView()
    select_all = MagicMock()
    add = MagicMock()
    view.select_all_requested.connect(select_all)
    view.add_requested.connect(add)

    QTest.keyClick(
        view,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.ControlModifier,
    )
    select_all.assert_called_once()
    add.assert_not_called()

    QTest.keyClick(view, Qt.Key.Key_Insert)
    add.assert_called_once()
