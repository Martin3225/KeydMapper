"""Custom button widget for controlling the KeyRecorder."""

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox, QPushButton

if TYPE_CHECKING:
    from keyd.key_recorder import KeyRecorder
    from PySide6.QtWidgets import QWidget


class RecordButton(QPushButton):
    """
    A button that toggles and displays the state of a KeyRecorder.
    It automatically updates its text and check state based on recording activity.
    """

    def __init__(self, recorder: "KeyRecorder", parent: "QWidget | None" = None):
        super().__init__("Record", parent)
        self._recorder = recorder
        self.setCheckable(True)
        self.setEnabled(False)

        self.clicked.connect(self._on_clicked)
        self._recorder.key_recorded.connect(self._on_key_recorded)
        self._recorder.error_occurred.connect(self._on_error)
        self.update_ui()

    def _on_clicked(self) -> None:
        """Toggles the recording state when the button is clicked."""
        self._recorder.toggle()
        self.update_ui()

    def _on_key_recorded(self, _: str) -> None:
        """Resets the UI state when a key is successfully recorded."""
        self.update_ui()

    def _on_error(self, message: str) -> None:
        """Called when the recorder encounters an error."""
        QMessageBox.warning(self, "Recording Error", message)
        self.update_ui()

    def reset(self) -> None:
        """Forces the recorder to stop and resets the button state."""
        self._recorder.stop()
        self.update_ui()

    def update_ui(self) -> None:
        """Updates the button's text and check state to match the recorder."""
        is_recording = self._recorder.is_recording
        self.setText("◼ Stop" if is_recording else "Record")
        self.setChecked(is_recording)
