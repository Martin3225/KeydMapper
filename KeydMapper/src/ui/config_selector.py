"""Minimal configuration list shown on the application home screen."""

import os

from constants import KEYD_CONFIG_PATH
from keyd.layout import get_device_id_from_config
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from ui.new_config_dialog import NewConfigDialog


class ConfigRowButton(QPushButton):  # pylint: disable=too-few-public-methods
    """One compact, keyboard-accessible configuration row."""

    def __init__(self, filename: str, device_id: str) -> None:
        super().__init__()
        self.filename = filename
        self.setMinimumHeight(58)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(14, 8, 14, 8)

        name = QLabel(filename)
        name.setStyleSheet("font-weight: bold;")
        row_layout.addWidget(name, stretch=3)

        device = QLabel(device_id or "Unknown device")
        device.setStyleSheet("color: #777;")
        row_layout.addWidget(device, stretch=3)

        enabled = filename.endswith(".conf")
        status = QLabel("Enabled" if enabled else "Disabled")
        status.setStyleSheet("color: #2e7d32;" if enabled else "color: #777;")
        row_layout.addWidget(status)

        arrow = QLabel("›")
        arrow.setStyleSheet("font-size: 20px;")
        row_layout.addWidget(arrow)


class ConfigSelector(QWidget):
    """Home screen listing available keyd configurations."""

    open_editor_requested = Signal(str, object)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        header_layout = QHBoxLayout()
        title = QLabel("Configurations")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.new_config_btn = QPushButton("+ New config")
        self.new_config_btn.clicked.connect(self.create_new_config)
        header_layout.addWidget(self.new_config_btn)
        layout.addLayout(header_layout)

        subtitle = QLabel("Choose a keyboard configuration to edit")
        subtitle.setStyleSheet("color: #777;")
        layout.addWidget(subtitle)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.content_widget = QWidget()
        self.list_layout = QVBoxLayout(self.content_widget)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(8)
        self.config_rows: list[ConfigRowButton] = []

        self._scroll_area.setWidget(self.content_widget)
        layout.addWidget(self._scroll_area)
        self.load_configs()

    def load_configs(self) -> None:
        """Scan keyd's directory and rebuild the compact configuration list."""
        while self.list_layout.count() > 0:
            item = self.list_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.config_rows = []

        try:
            files = sorted(
                filename
                for filename in os.listdir(KEYD_CONFIG_PATH)
                if filename.endswith((".conf", ".disabled"))
            )
        except PermissionError:
            files = []
        except FileNotFoundError:
            files = []

        if not files:
            empty_state = QLabel(
                "No configurations yet.\nCreate your first config to get started."
            )
            empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_state.setStyleSheet("color: #777; padding: 40px;")
            self.list_layout.addWidget(empty_state)
            return

        for filename in files:
            row = ConfigRowButton(
                filename,
                get_device_id_from_config(filename),
            )
            row.clicked.connect(
                lambda checked=False, config_name=filename: self._config_click(
                    config_name
                )
            )
            self.config_rows.append(row)
            self.list_layout.addWidget(row)

    def _config_click(self, filename: str) -> None:
        """Open an existing configuration."""
        self.open_editor_requested.emit(filename, None)

    def create_new_config(self) -> None:
        """Open the existing dialog for creating a configuration."""
        dialog = NewConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.open_editor_requested.emit(dialog.config_name, dialog.device_id)
