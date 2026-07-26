"""Represents an individual keyboard key in the visual scene."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

KEY_MIN_WIDTH: int = 20
KEY_MIN_HEIGHT: int = 20
KEY_DEFAULT_WIDTH: int = 60
KEY_DEFAULT_HEIGHT: int = 60
SNAP_GRID: int = 10
HANDLE_SIZE: int = 10
CORNER_RADIUS: int = 4
BORDER_WIDTH: int = 1
TEXT_PADDING: int = 2

# Colors
COLOR_OVERLAP_FILL = QColor("#c0392b")
COLOR_OVERLAP_BORDER = QColor("#e74c3c")
COLOR_SELECTED_FILL = QColor("#2980b9")
COLOR_SELECTED_BORDER = QColor("#5dade2")
COLOR_CHANGED_FILL = QColor("#27ae60")
COLOR_CHANGED_BORDER = QColor("#2ecc71")
COLOR_CHANGED_SELECTED_FILL = QColor("#1e8449")
COLOR_CHANGED_SELECTED_BORDER = QColor("#27ae60")
COLOR_DEFAULT_FILL = QColor("#4a7cb8")
COLOR_DEFAULT_BORDER = QColor("#6a9cd8")
COLOR_HANDLE_FILL = QColor("white")
COLOR_TEXT = QColor("white")


class DragMode(Enum):
    """Enumeration of possible dragging operations. Values 0-3 match handle indices."""

    NONE = -1
    MOVE = -2
    TOP_LEFT = 0
    TOP_RIGHT = 1
    BOTTOM_LEFT = 2
    BOTTOM_RIGHT = 3


@dataclass
class DragState:
    """Encapsulates the state required for dragging operations."""

    mode: DragMode = DragMode.NONE
    origin: QPointF | None = None
    saved_pos: QPointF | None = None
    saved_rect: QRectF | None = None


def snap(val: float) -> float:
    """Snaps a value to the grid defined by SNAP_GRID."""
    return round(val / SNAP_GRID) * SNAP_GRID


class KeyItem(QGraphicsItem):
    """
    Interactive key item for the keyboard layout.
    Supports selecting and assigning values.
    """

    # Class-level variable to track items being dragged together
    _drag_group: list[tuple[KeyItem, QPointF]] = []

    def __init__(
        self,
        name: str,
        value: str,
        geometry: QRectF,
        locked: bool = False,
    ):
        """Initializes a new KeyItem with name, value, geometry, and locked state."""
        super().__init__()
        self.key_name = name
        self.key_value = value
        self.rect = QRectF(0, 0, geometry.width(), geometry.height())
        self.setPos(geometry.x(), geometry.y())
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.locked = locked

        self._drag_state = DragState()
        self.overlapping = False

    def boundingRect(self) -> QRectF:
        """Defines the outer boundaries of the item for redrawing and collision."""
        return self.rect.adjusted(-1, -1, 1, 1)

    def _get_colors(self) -> tuple[QColor, QColor]:
        """Determines the fill and border colors based on the current state."""
        if self.overlapping:
            return COLOR_OVERLAP_FILL, COLOR_OVERLAP_BORDER

        is_changed = bool(self.key_value)
        is_selected = self.isSelected()

        if is_selected and is_changed:
            return COLOR_CHANGED_SELECTED_FILL, COLOR_CHANGED_SELECTED_BORDER
        if is_selected:
            return COLOR_SELECTED_FILL, COLOR_SELECTED_BORDER
        if is_changed:
            return COLOR_CHANGED_FILL, COLOR_CHANGED_BORDER

        return COLOR_DEFAULT_FILL, COLOR_DEFAULT_BORDER

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """Paints the key, its label, and resize handles if selected."""
        _ = option, widget  # Unused by design
        fill, border = self._get_colors()

        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, BORDER_WIDTH))
        painter.drawRoundedRect(self.rect, CORNER_RADIUS, CORNER_RADIUS)

        if self.isSelected() and not self.locked:
            painter.setBrush(QBrush(COLOR_HANDLE_FILL))
            painter.setPen(Qt.PenStyle.NoPen)
            for handle_rect in self._handle_rects():
                painter.drawRect(handle_rect)

        painter.setPen(QPen(COLOR_TEXT))
        display_text = self.key_value if self.key_value else self.key_name

        painter.drawText(
            self.rect.adjusted(
                TEXT_PADDING, TEXT_PADDING, -TEXT_PADDING, -TEXT_PADDING
            ),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            display_text,
        )

    def check_overlap(self) -> bool:
        """Checks if this item or its drag group overlap with other KeyItems."""
        all_moved = [self] + [item for item, _ in KeyItem._drag_group]
        for item in all_moved:
            colliding = item.scene().collidingItems(item) if item.scene() else []
            if any(isinstance(c, KeyItem) and c not in all_moved for c in colliding):
                return True
        return False

    def update_overlap(self) -> None:
        """Updates the overlapping visual state for this item and its drag group."""
        is_overlapping = self.check_overlap()
        all_moved = [self] + [item for item, _ in KeyItem._drag_group]
        if is_overlapping != self.overlapping:
            for item in all_moved:
                item.overlapping = is_overlapping
                item.update()

    def _handle_rects(self) -> list[QRectF]:
        """Returns the rectangles for the four resize handles in the corners."""
        rect, size = self.rect, HANDLE_SIZE
        return [
            QRectF(rect.left(), rect.top(), size, size),
            QRectF(rect.right() - size, rect.top(), size, size),
            QRectF(rect.left(), rect.bottom() - size, size, size),
            QRectF(rect.right() - size, rect.bottom() - size, size, size),
        ]

    def _get_drag_mode(self, mouse_pos: QPointF) -> DragMode:
        """Returns the DragMode based on which handle is at the mouse position."""
        if not self.isSelected() or self.locked:
            return DragMode.NONE

        for index, handle_rect in enumerate(self._handle_rects()):
            if handle_rect.contains(mouse_pos):
                return DragMode(index)

        return DragMode.NONE

    def mousePressEvent(self, event) -> None:
        """Handles mouse press to start moving or resizing."""
        if event.button() == Qt.MouseButton.LeftButton:
            handle_mode = self._get_drag_mode(event.pos())
            self._drag_state.mode = (
                handle_mode if handle_mode != DragMode.NONE else DragMode.MOVE
            )
            if self.locked:
                self._drag_state.mode = DragMode.NONE
            self._drag_state.origin = event.scenePos()
            self._drag_state.saved_pos = self.pos()
            self._drag_state.saved_rect = QRectF(self.rect)

            if self._drag_state.mode == DragMode.MOVE and self.isSelected():
                KeyItem._drag_group = [
                    (item, item.pos())
                    for item in self.scene().selectedItems()
                    if isinstance(item, KeyItem) and item is not self
                ]
            else:
                KeyItem._drag_group = []
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Handles mouse movement to update position or size during drag."""
        if self._drag_state.mode == DragMode.NONE or self._drag_state.origin is None:
            return
        delta = event.scenePos() - self._drag_state.origin
        snap_grid = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        if self._drag_state.mode == DragMode.MOVE:
            self._apply_move(delta, snap_grid)
        else:
            self._apply_resize(delta, snap_grid)

        self.update_overlap()

    def mouseReleaseEvent(self, event) -> None:
        """Handles mouse release to finalize movement or revert if overlapping."""
        _ = event
        if (
            self.overlapping
            and self._drag_state.saved_pos is not None
            and self._drag_state.saved_rect is not None
        ):
            self.prepareGeometryChange()
            self.rect = QRectF(self._drag_state.saved_rect)
            self.setPos(self._drag_state.saved_pos)
            for item, saved in KeyItem._drag_group:
                item.setPos(saved)
                item.overlapping = False
                item.update()

        self.overlapping = False
        self._drag_state.mode = DragMode.NONE
        KeyItem._drag_group = []
        self.update()
        super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event) -> None:
        """Changes the cursor shape when hovering over resize handles."""
        handle_mode = self._get_drag_mode(event.pos())
        if self.locked:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif handle_mode in (DragMode.TOP_LEFT, DragMode.BOTTOM_RIGHT):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif handle_mode in (DragMode.TOP_RIGHT, DragMode.BOTTOM_LEFT):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif self.isSelected():
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def hoverLeaveEvent(self, event) -> None:
        """Resets the cursor when the mouse leaves the item."""
        _ = event
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _apply_move(self, delta: QPointF, snap_grid: bool) -> None:
        """Applies movement to the item and its drag group, with optional snapping."""
        assert self._drag_state.saved_pos is not None

        def get_pos(orig: QPointF) -> QPointF:
            new_x = orig.x() + delta.x()
            new_y = orig.y() + delta.y()
            if snap_grid:
                return QPointF(snap(new_x), snap(new_y))
            return QPointF(new_x, new_y)

        self.setPos(get_pos(self._drag_state.saved_pos))
        for item, saved in KeyItem._drag_group:
            item.setPos(get_pos(saved))

    def _apply_resize(self, delta: QPointF, snap_grid: bool) -> None:
        """Applies resizing to the item based on the dragged handle."""
        assert (
            self._drag_state.saved_pos is not None
            and self._drag_state.saved_rect is not None
            and self._drag_state.mode != DragMode.NONE
        )

        new_left = self._drag_state.saved_pos.x()
        new_top = self._drag_state.saved_pos.y()
        new_right = new_left + self._drag_state.saved_rect.width()
        new_bottom = new_top + self._drag_state.saved_rect.height()

        # Determine which sides are affected based on the DragMode
        is_left = self._drag_state.mode in (DragMode.TOP_LEFT, DragMode.BOTTOM_LEFT)
        is_right = self._drag_state.mode in (DragMode.TOP_RIGHT, DragMode.BOTTOM_RIGHT)
        is_top = self._drag_state.mode in (DragMode.TOP_LEFT, DragMode.TOP_RIGHT)
        is_bottom = self._drag_state.mode in (DragMode.BOTTOM_LEFT, DragMode.BOTTOM_RIGHT)

        if is_left:
            new_left = self._drag_state.saved_pos.x() + delta.x()
            new_left = min(new_left, new_right - KEY_MIN_WIDTH)

        if is_right:
            new_right = self._drag_state.saved_pos.x() + self._drag_state.saved_rect.width() + delta.x()
            new_right = max(new_right, new_left + KEY_MIN_WIDTH)

        if is_top:
            new_top = self._drag_state.saved_pos.y() + delta.y()
            new_top = min(new_top, new_bottom - KEY_MIN_HEIGHT)

        if is_bottom:
            new_bottom = self._drag_state.saved_pos.y() + self._drag_state.saved_rect.height() + delta.y()
            new_bottom = max(new_bottom, new_top + KEY_MIN_HEIGHT)

        if snap_grid:
            new_left = snap(new_left)
            new_right = snap(new_right)
            new_top = snap(new_top)
            new_bottom = snap(new_bottom)

        self.prepareGeometryChange()
        self.rect = QRectF(0, 0, new_right - new_left, new_bottom - new_top)
        self.setPos(new_left, new_top)
