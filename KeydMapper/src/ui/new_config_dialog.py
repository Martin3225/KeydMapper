"""Dialog for creating a new keyd configuration file."""

import os

from constants import KEYD_CONFIG_PATH
from keyd.devices import get_devices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class NewConfigDialog(QDialog):
    """
    A dialog that allows the user to specify a name and target device
    for a new keyd configuration.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("New Configuration")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Enter new config name:"))

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g., my_layout.conf")
        layout.addWidget(self._name_input)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: red;")
        layout.addWidget(self._error_label)

        layout.addWidget(QLabel("Select device:"))

        device_hbox = QHBoxLayout()
        self._device_dropdown = QComboBox()
        self._device_id_input = QLineEdit()

        self.devices: dict[str, str] = get_devices()
        for device_id, name in self.devices.items():
            self._device_dropdown.addItem(f"{name} ({device_id})", userData=device_id)
        if self.devices:
            self._device_id_input.setText(self._device_dropdown.currentData() or "")

        self._device_dropdown.currentIndexChanged.connect(
            lambda idx: self._device_id_input.setText(
                self._device_dropdown.itemData(idx) or ""
            )
        )

        device_hbox.addWidget(self._device_dropdown, stretch=2)
        device_hbox.addWidget(self._device_id_input, stretch=1)
        layout.addLayout(device_hbox)

        button_layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_ok)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    @property
    def config_name(self) -> str:
        """Returns the sanitized configuration filename."""
        name = self._name_input.text().strip()
        if name and not name.endswith((".conf", ".disabled")):
            name += ".conf"
        return name

    @property
    def device_id(self) -> str:
        """Returns the specified device ID (vendor:product)."""
        return self._device_id_input.text()

    def _on_ok(self):
        """Validates the input and accepts the dialog if valid."""
        error = self._validate()
        if error:
            self._error_label.setText(error)
        else:
            self.accept()

    def _validate(self) -> str | None:
        """Checks for naming conflicts and invalid characters."""
        name = self.config_name
        if not name:
            return "Name cannot be empty."
        if len(name) > 100:
            return "Name is too long (max 100 chars)."
        for char in ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]:
            if char in name:
                return f"Invalid character: {char}"
        if os.path.exists(os.path.join(KEYD_CONFIG_PATH, name)):
            return "A config with this name already exists."
        return None
