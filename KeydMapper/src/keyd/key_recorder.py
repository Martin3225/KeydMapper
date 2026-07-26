"""Module for recording key presses using keyd monitor."""

import re

from PySide6.QtCore import QObject, QProcess, Signal


class KeyRecorder(QObject):
    """Recorder that listens to keyd monitor and emits signals for recorded keys."""

    key_recorded = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, device_id: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._device_id = device_id
        self._process: QProcess | None = None

    @property
    def is_recording(self) -> bool:
        """Returns True if the recorder is currently active."""
        return self._process is not None

    def start(self) -> None:
        """Starts the keyd monitor process."""
        if self._process is not None:
            return
        self._process = QProcess(self)
        self._process.errorOccurred.connect(self._on_error)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.start("keyd", ["monitor"])

    def stop(self) -> None:
        """Stops the keyd monitor process."""
        if self._process is not None:
            try:
                self._process.errorOccurred.disconnect(self._on_error)
            except RuntimeError:
                pass
            self._process.kill()
            self._process.waitForFinished(200)
            self._process = None

    def toggle(self) -> None:
        """Toggles the recording state."""
        if self.is_recording:
            self.stop()
        else:
            self.start()

    def _on_error(self, error: QProcess.ProcessError) -> None:
        """Handles process errors, such as keyd not being installed."""
        if error == QProcess.ProcessError.FailedToStart:
            self.error_occurred.emit("Failed to start keyd. Is it installed?")
        else:
            self.error_occurred.emit("An error occurred with the keyd process.")
        self.stop()

    def _on_output(self) -> None:
        """Handles output from the keyd monitor process."""
        if self._process is None:
            return
        raw = self._process.readAllStandardOutput().toStdString()
        pattern = re.compile(r"(\w+(?::\w+)+)\s+(\S+)\s+down", re.MULTILINE)
        for match in pattern.finditer(raw):
            full_id, key_name = match.group(1), match.group(2)
            if self._device_id is None or full_id.startswith(self._device_id):
                self.stop()
                self.key_recorded.emit(key_name)
                return
