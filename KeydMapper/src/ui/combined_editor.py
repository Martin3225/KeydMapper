"""Main editor widget with one integrated binding/layout workspace."""



from keyd.config import Config
from keyd.layout import does_layout_exist
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
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
    Main container for editing a keyd configuration in one persistent shell.
    Physical layout editing reuses the same scene, canvas and inspector.
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

        self.layout_editor = LayoutEditor(
            device_id=self.device_id,
            scene=self.shared_scene,
            view=self.shared_view,
        )

        self.config_editor = ConfigEditor(
            config=self.config,
            scene=self.shared_scene,
            view=self.shared_view,
            layout_editor=self.layout_editor,
        )
        self.config_editor.cancel_requested.connect(self.closed.emit)
        layout.addWidget(self.config_editor)

        self.config_editor.attach_view()
        self.config_editor.activate_mode()
        if not does_layout_exist(self.device_id):
            self.config_editor.enter_layout_mode()

        # Center the view on the scene
        self.shared_view.centerOn(SCENE_WIDTH / 2, SCENE_HEIGHT / 2)
