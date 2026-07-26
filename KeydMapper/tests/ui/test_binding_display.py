"""Tests for compact visual-key labels and their lossless tooltips."""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStyleOptionGraphicsItem
from ui.binding_display import display_for_key
from ui.key_item import KeyItem


def test_oneshot_macro_uses_semantic_label_and_badge():
    """Long internal syntax becomes two short lines plus a macro badge."""
    display = display_for_key(
        "capslock",
        "oneshotm(nav, macro(leftmouse))",
    )

    assert display.title == "ONESHOT"
    assert display.detail == "nav"
    assert display.badge == "+M"
    assert display.tooltip == (
        "capslock = oneshotm(nav, macro(leftmouse))"
    )


def test_oneshot_held_key_uses_key_badge():
    """Held-key oneshot variants use a distinct compact badge."""
    display = display_for_key("capslock", "oneshotk(nav, a)")

    assert display.title == "ONESHOT"
    assert display.detail == "nav"
    assert display.badge == "+K"


def test_nested_overload_is_summarized_instead_of_reproduced():
    """Nested expressions are described semantically on the key."""
    display = display_for_key(
        "mouse1",
        "overload(control, macro(leftmouse))",
    )

    assert display.title == "TAP · Left click"
    assert display.detail == "HOLD · control"
    assert "overload(" not in display.detail


def test_overload_repeated_mouse_macro_shows_click_count():
    """Repeated mouse tokens remain recognizable without an ellipsized macro."""
    display = display_for_key(
        "mouse1",
        "overload(media, macro(leftmouse leftmouse))",
    )

    assert display.title == "TAP · 2× Left click"
    assert display.detail == "HOLD · media"
    assert display.tooltip == (
        "mouse1 = overload(media, macro(leftmouse leftmouse))"
    )


def test_small_mouse_buttons_have_stable_human_labels():
    """Wheel and middle buttons use labels suited to their small geometry."""
    assert display_for_key("scrollup", "").title == "WHEEL"
    assert display_for_key("scrollup", "").detail == "↑"
    assert display_for_key("middlemouse", "").title == "MIDDLE"
    assert display_for_key("scrolldown", "").detail == "↓"


def test_mouse_name_used_as_a_binding_is_compacted_too():
    """Mouse aliases are compact whether they are inputs or binding outputs."""
    display = display_for_key("a", "middlemouse")

    assert display.title == "MIDDLE"
    assert display.tooltip == "a = middlemouse"


def test_key_item_tooltip_keeps_exact_names_after_compacting():
    """Compaction never removes the exact editable value from the tooltip."""
    item = KeyItem("middlemouse", "", QRectF(0, 0, 40, 60))
    assert item.toolTip() == "middlemouse"

    item.key_value = "oneshotm(nav, macro(leftmouse))"
    assert item.toolTip() == (
        "middlemouse = oneshotm(nav, macro(leftmouse))"
    )


def test_small_key_label_paints_without_wrapping_raw_config():
    """Exercise the real painter path at the mouse wheel's 40px size."""
    item = KeyItem(
        "scrollup",
        "oneshotm(nav, macro(leftmouse))",
        QRectF(0, 0, 40, 40),
    )
    image = QImage(44, 44, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)

    item.paint(painter, QStyleOptionGraphicsItem())

    painter.end()
    assert item.display_content.title == "ONESHOT"
    assert item.display_content.badge == "+M"
