"""Widget for selecting or creating keyd configuration files."""

import os

from constants import KEYD_CONFIG_PATH
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from ui.new_config_dialog import NewConfigDialog


class ConfigSelector(QWidget):
    """
    Displays a grid of available keyd configurations.
    Allows users to select an existing config or initiate the creation of a new one.
    """

    open_editor_requested = Signal(str, object)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        header = QLabel("Select config to modify")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(header)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)

        self.content_widget = QWidget()
        self.grid_layout = QGridLayout(self.content_widget)
        self.grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.load_configs()

        self._scroll_area.setWidget(self.content_widget)
        layout.addWidget(self._scroll_area)

    def load_configs(self):
        """Scans the config directory and populates the grid with configuration buttons."""
        # Clear existing widgets
        while self.grid_layout.count() > 0:
            item = self.grid_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        files = []
        try:
            files = [
                f
                for f in os.listdir(KEYD_CONFIG_PATH)
                if f.endswith((".conf", ".disabled"))
            ]
        except PermissionError:
            print("Error: User does not have permission to read " + KEYD_CONFIG_PATH)
        except FileNotFoundError:
            files = ["file_not_found.conf"]

        files = ["New config", *files]

        cols = max(1, self._scroll_area.viewport().width() // 160)
        for index, filename in enumerate(files):
            btn = QPushButton(filename)
            btn.setFixedSize(150, 100)
            btn.setStyleSheet(
                "background-color: #333; color: white; border-radius: 8px;"
            )
            self.grid_layout.addWidget(btn, index // cols, index % cols)
            btn.clicked.connect(lambda ch=False, f=filename: self._config_click(f))

    def _config_click(self, filename: str):
        """Handles a click on a configuration button."""
        if filename == "New config":
            self.create_new_config()
        else:
            self.open_editor_requested.emit(filename, None)

    def create_new_config(self):
        """Opens the dialog to create a new configuration."""
        dialog = NewConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.open_editor_requested.emit(dialog.config_name, dialog.device_id)
