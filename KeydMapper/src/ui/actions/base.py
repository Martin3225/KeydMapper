"""Base classes for modular action widgets in the configuration editor."""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from ui.key_item import KeyItem

if TYPE_CHECKING:
    from ui.config_editor import ConfigEditor


class ConfigActionWidget(QWidget):
    """Base class for modular actions in the ConfigEditor side panel."""

    def __init__(self, editor: "ConfigEditor"):
        super().__init__()
        self.editor = editor

    def on_selection_changed(self, key_item: KeyItem | None) -> None:
        """Called when the scene selection changes."""

    def on_layer_changed(self, layer: str) -> None:
        """Called when the active config layer changes."""
