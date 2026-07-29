"""Main application window for KeydMapper."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget
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

        self._application_actions: dict[str, QAction] = {}
        self._add_application_action(
            "new_config",
            "New Configuration",
            ["Ctrl+N"],
            self._create_new_config,
        )
        self._quit_action = self._add_application_action(
            "quit",
            "Quit",
            ["Ctrl+Q"],
            self.close,
        )
        self._add_application_action(
            "shortcuts",
            "Keyboard Shortcuts",
            ["F1", "Ctrl+?"],
            self._show_keyboard_shortcuts,
        )

        self._selector_page = ConfigSelector()
        self._selector_page.open_editor_requested.connect(self.show_combined_editor)
        self._stacked.addWidget(self._selector_page)

    def _add_application_action(
        self,
        name: str,
        text: str,
        shortcuts: list[str],
        callback,
    ) -> QAction:
        """Register one application-wide keyboard command."""
        action = QAction(text, self)
        action.setShortcuts([QKeySequence(shortcut) for shortcut in shortcuts])
        action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        action.triggered.connect(callback)
        self.addAction(action)
        self._application_actions[name] = action
        return action

    def _create_new_config(self) -> None:
        """Open the new-configuration dialog from any application page."""
        self._selector_page.create_new_config()

    def _show_keyboard_shortcuts(self) -> None:
        """Show the keyboard commands available in each application context."""
        QMessageBox.information(
            self,
            "Keyboard Shortcuts",
            "Application\n"
            "Ctrl+N        New configuration\n"
            "Ctrl+Q        Quit\n"
            "F1 / Ctrl+?   Show this help\n\n"
            "Configuration editor\n"
            "Ctrl+S        Save and apply\n"
            "Ctrl+Shift+F  Format generated config\n"
            "Ctrl+Z        Undo\n"
            "Ctrl+Shift+Z  Redo\n"
            "Esc           Back / leave physical-layout mode\n"
            "F2            Rename selected layer\n"
            "Ctrl+Space    Show source suggestions\n"
            "Alt+Up/Down   Move source lines\n\n"
            "Physical-layout canvas\n"
            "Insert        Add key\n"
            "Delete        Delete selected keys\n"
            "Ctrl+A        Select all keys\n"
            "Ctrl+C / V    Copy / paste keys",
        )

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
