"""Shared context objects for the UI components."""

from dataclasses import dataclass

from PySide6.QtWidgets import QGraphicsScene
from ui.layout_view import LayoutView


@dataclass
class EditorContext:
    """Bundles shared resources for the editor."""

    scene: QGraphicsScene
    view: LayoutView
