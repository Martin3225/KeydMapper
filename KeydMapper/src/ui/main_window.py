"""Main application window for KeydMapper."""

from PySide6.QtWidgets import QMainWindow, QStackedWidget
from ui.combined_editor import CombinedEditor
from ui.config_selector import ConfigSelector


class MainWindow(QMainWindow):
    """
    The root window of the application.
    Manages switching between the configuration selector and the combined editor.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("KeydMapper")

        self._stacked = QStackedWidget()
        self.setCentralWidget(self._stacked)
        self.resize(1280, 800)

        self._selector_page = ConfigSelector()
        self._selector_page.open_editor_requested.connect(self.show_combined_editor)
        self._stacked.addWidget(self._selector_page)

    def show_config_selector(self):
        """Switches the view back to the configuration selection screen."""
        self._selector_page.load_configs()
        self._stacked.setCurrentIndex(0)
        while self._stacked.count() > 1:
            w = self._stacked.widget(self._stacked.count() - 1)
            if w is not None:
                if isinstance(w, CombinedEditor):
                    w.shutdown()
                self._stacked.removeWidget(w)
                w.deleteLater()

    def show_combined_editor(self, config_name: str, device_id: str | None = None):
        """Initializes and shows the combined editor for a specific configuration."""
        if not config_name:
            return

        page = CombinedEditor(
            config_name=config_name,
            device_id=device_id,
        )
        page.closed.connect(self.show_config_selector)
        self._stacked.addWidget(page)
        self._stacked.setCurrentWidget(page)

    # pylint: disable=invalid-name
    def closeEvent(self, event) -> None:
        """Shut down editors before Qt deletes their shared C++ resources."""
        for index in range(self._stacked.count()):
            page = self._stacked.widget(index)
            if isinstance(page, CombinedEditor):
                page.shutdown()
        super().closeEvent(event)
