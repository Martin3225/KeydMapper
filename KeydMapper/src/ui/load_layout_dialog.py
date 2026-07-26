"""Dialog for choosing an existing layout file to load into the editor."""

import os

from constants import LAYOUTS_PATH
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LoadLayoutDialog(QDialog):
    """A dialog that lists available .layout files and allows the user to select one."""

    # pylint: disable=too-few-public-methods

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Load Layout")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a layout to load:"))

        self._list = QListWidget()
        try:
            files = sorted(f for f in os.listdir(LAYOUTS_PATH) if f.endswith(".layout"))
        except FileNotFoundError:
            files = []
        for f in files:
            self._list.addItem(f)
        self._list.doubleClicked.connect(self._on_load)
        layout.addWidget(self._list)

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        ok = QPushButton("Load")
        ok.setDefault(True)
        ok.clicked.connect(self._on_load)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

        self._selected_path: str | None = None

    def _on_load(self) -> None:
        """Handles the selection of a layout and closes the dialog."""
        item = self._list.currentItem()
        if item:
            self._selected_path = os.path.join(LAYOUTS_PATH, item.text())
            self.accept()

    @property
    def selected_path(self) -> str | None:
        """Returns the absolute path to the selected layout file."""
        return self._selected_path
