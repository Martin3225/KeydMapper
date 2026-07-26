"""Custom QGraphicsView for navigating and interacting with the layout scene."""

import warnings

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QGraphicsView

SCENE_WIDTH: int = 5000
SCENE_HEIGHT: int = 2500

MIN_ZOOM: float = 0.2
MAX_ZOOM: float = 2.0


class LayoutView(QGraphicsView):
    """
    A graphics view that supports zooming, panning, and keyboard shortcuts.
    It manages the visual representation of the keyboard layout scene.
    """

    delete_requested = Signal()
    add_requested = Signal()
    copy_requested = Signal()
    paste_requested = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self._pan_active = False
        self._pan_last: QPoint | None = None

    # @generated [partially] Gemini 3.1: Fix RuntimeError when disconnecting signals
    def disconnect_signals(self) -> None:
        """Safely disconnects all custom signals."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                self.delete_requested.disconnect()
                self.add_requested.disconnect()
                self.copy_requested.disconnect()
                self.paste_requested.disconnect()
            except RuntimeError:
                pass  # Ignore if no slots were connected

    # Qt framwork invalid methods names
    # pylint: disable=invalid-name
    def keyPressEvent(self, event) -> None:
        """Handles global keyboard shortcuts for the editor."""
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        key = event.key()
        if key == Qt.Key.Key_Delete:
            self.delete_requested.emit()
        elif key == Qt.Key.Key_C and ctrl:
            self.copy_requested.emit()
        elif key == Qt.Key.Key_V and ctrl:
            self.paste_requested.emit()
        elif key == Qt.Key.Key_A and ctrl:
            self.add_requested.emit()
        else:
            super().keyPressEvent(event)

    # Qt framwork invalid methods names
    # pylint: disable=invalid-name
    def mousePressEvent(self, event) -> None:
        """Initiates panning when the middle mouse button is pressed."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = True
            self._pan_last = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    # pylint: disable=invalid-name
    def mouseMoveEvent(self, event) -> None:
        """Handles panning movement."""
        if self._pan_active and self._pan_last is not None:
            delta = event.position().toPoint() - self._pan_last
            self._pan_last = event.position().toPoint()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    # pylint: disable=invalid-name
    def mouseReleaseEvent(self, event) -> None:
        """Ends panning when the middle mouse button is released."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = False
            self._pan_last = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # pylint: disable=invalid-name
    def wheelEvent(self, event) -> None:
        """Handles zooming with the mouse wheel, centered on the cursor position."""
        current = self.transform().m11()
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        new_zoom = current * factor
        if new_zoom < MIN_ZOOM:
            factor = MIN_ZOOM / current
        elif new_zoom > MAX_ZOOM:
            factor = MAX_ZOOM / current
        if abs(factor - 1.0) < 1e-9:
            return
        cursor_scene = self.mapToScene(event.position().toPoint())
        self.scale(factor, factor)
        shifted = self.mapToScene(event.position().toPoint())
        delta = shifted - cursor_scene
        self.translate(delta.x(), delta.y())
