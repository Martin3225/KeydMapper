"""Main editor widget that combines layout and configuration editing in tabs."""



from keyd.config import Config
from keyd.layout import does_layout_exist
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Signal
from ui.config_editor import ConfigEditor
from ui.layout_editor import LayoutEditor
from ui.layout_view import SCENE_HEIGHT, SCENE_WIDTH, LayoutView


# @generated [partially] Gemini 3.1: Graphics and styling adjustments, doc strings
# Number of attributes is high due to the UI layout
# pylint: disable=too-many-instance-attributes,too-few-public-methods
class CombinedEditor(QWidget):
    """
    Main container for editing a keyd configuration.
    It manages a shared QGraphicsScene and LayoutView between two modes:
    Layout (positioning keys) and Config (mapping keys to actions).
    """

    closed = Signal()

    def __init__(
        self,
        config_name: str,
        device_id: str | None,
    ):
        super().__init__()

        self.config = Config(config_name, device_id)
        self.device_id = self.config.device_id

        # Create Shared Scene and View
        self.shared_scene = QGraphicsScene(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self.shared_scene.setBackgroundBrush(QBrush(QColor("#1e1e1e")))

        self.shared_view = LayoutView(self.shared_scene)
        self.shared_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.shared_view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.layout_editor = LayoutEditor(
            device_id=self.device_id,
            scene=self.shared_scene,
            view=self.shared_view,
        )
        self.layout_editor.layout_done.connect(self._on_layout_done)
        self.layout_editor.cancel_requested.connect(self.closed.emit)

        self.config_editor = ConfigEditor(
            config=self.config,
            scene=self.shared_scene,
            view=self.shared_view,
        )
        self.config_editor.cancel_requested.connect(self.closed.emit)

        self.tabs.addTab(self.layout_editor, "Layout")
        self.tabs.addTab(self.config_editor, "Config")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Initial selection
        if not does_layout_exist(self.device_id):
            self.tabs.setCurrentWidget(self.layout_editor)
        else:
            self.tabs.setCurrentWidget(self.config_editor)

        # Manually trigger the first setup
        self._on_tab_changed(self.tabs.currentIndex())

        # Center the view on the scene
        self.shared_view.centerOn(SCENE_WIDTH / 2, SCENE_HEIGHT / 2)

    def _on_tab_changed(self, index: int) -> None:
        """Handles switching between editor modes by re-attaching the shared view."""
        editor = self.tabs.widget(index)
        if isinstance(editor, (LayoutEditor, ConfigEditor)):
            editor.attach_view()
            editor.activate_mode()

    def _on_layout_done(self) -> None:
        """Called when layout editing is finished, switches to configuration editing."""
        self.tabs.setCurrentWidget(self.config_editor)
