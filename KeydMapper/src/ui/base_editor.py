"""Base editor widget providing a common layout for configuration and layout editing."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from ui.context import EditorContext
from ui.key_item import KeyItem


# Number of attributes is high due to the UI layout
# pylint: disable=too-many-instance-attributes
class BaseEditor(QWidget):
    """
    Base widget for all editor modes.
    Provides a top toolbar, a central splitter with a side panel, and bottom buttons.
    """

    save_requested = Signal()
    cancel_requested = Signal()

    def __init__(
        self,
        context: EditorContext,
    ):
        super().__init__()

        self._root_layout = QVBoxLayout(self)

        # Toolbar
        self.toolbar_layout = QHBoxLayout()
        self._root_layout.addLayout(self.toolbar_layout)

        # Content area (View + Side Panel)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setOpaqueResize(True)
        self._root_layout.addWidget(self._splitter, stretch=10)

        # Scene and View (Stored but NOT added to layout yet)
        self._scene = context.scene
        self._view = context.view
        self._context_attached = True
        self._scene.selectionChanged.connect(self._on_selection_changed)
        self._scene.destroyed.connect(self._on_scene_destroyed)

        # Side Panel
        self.side_panel = QFrame()
        self.side_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.side_panel.setMinimumWidth(200)
        self.panel_layout = QVBoxLayout(self.side_panel)
        self.panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._splitter.addWidget(self.side_panel)

        self._overlay = QLabel("Select key", self.side_panel)
        self._overlay.setStyleSheet(
            "background-color: rgba(0, 0, 0, 180);"
            "color: white;"
            "font-size: 16px;"
            "font-weight: bold;"
        )
        self._overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.side_panel.installEventFilter(self)

        # Bottom Buttons
        self.bottom_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_requested)
        self.bottom_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_requested)
        self.bottom_layout.addWidget(self.save_btn)
        self._root_layout.addLayout(self.bottom_layout)

    def attach_view(self) -> None:
        """Attaches the shared view to this editor's layout."""
        if self._splitter.indexOf(self._view) != -1:
            return
        self._splitter.insertWidget(0, self._view)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([900, 260])

    def activate_mode(self) -> None:
        """Called when this editor mode becomes active."""

    def showEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Handles widget show events."""
        super().showEvent(event)
        self._view.viewport().update()
        self._overlay.raise_()

    def eventFilter(self, obj, event) -> bool:  # pylint: disable=invalid-name
        """Filters events for the side panel overlay."""
        if obj == self.side_panel and event.type() == event.Type.Resize:
            self._overlay.resize(event.size())
        return super().eventFilter(obj, event)

    def _on_selection_changed(self) -> None:
        """Updates the UI when the selection in the scene changes."""
        key = self.get_selected_key_item()
        if key:
            self._overlay.hide()
        else:
            self._overlay.show()
            self._overlay.raise_()

    def get_selected_key_item(self) -> KeyItem | None:
        """Returns the currently selected KeyItem, if any."""
        if not self._context_attached:
            return None
        items = [i for i in self._scene.selectedItems() if isinstance(i, KeyItem)]
        return items[0] if items else None

    def _on_scene_destroyed(self) -> None:
        """Mark the context unusable before queued selection callbacks can run."""
        self._context_attached = False

    def shutdown(self) -> None:
        """Disconnect shared Qt resources before their C++ objects are deleted."""
        if not self._context_attached:
            return
        self._context_attached = False
        try:
            self._scene.selectionChanged.disconnect(self._on_selection_changed)
        except (RuntimeError, TypeError):
            pass
        try:
            self._scene.destroyed.disconnect(self._on_scene_destroyed)
        except (RuntimeError, TypeError):
            pass

    # pylint: disable=invalid-name
    def closeEvent(self, event) -> None:
        """Detach shared resources before closing an independently owned editor."""
        self.shutdown()
        super().closeEvent(event)
