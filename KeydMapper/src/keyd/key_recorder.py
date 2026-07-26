"""Module for recording key presses using keyd monitor."""

import os
import re
import shutil

from PySide6.QtCore import QObject, QProcess, Signal


class KeyRecorder(QObject):
    """Recorder that listens to keyd monitor and emits signals for recorded keys."""

    key_recorded = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, device_id: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._device_id = device_id if device_id not in {"", "*"} else None
        self._process: QProcess | None = None
        self._stderr = ""
        self._stdout = ""
        self._uses_polkit = False

    @property
    def is_recording(self) -> bool:
        """Returns True if the recorder is currently active."""
        return self._process is not None

    def start(self) -> None:
        """Start a privileged physical-device monitor through Polkit."""
        if self._process is not None:
            return

        keyd_path = shutil.which("keyd")
        if keyd_path is None:
            self.error_occurred.emit(
                "keyd was not found. Install keyd before recording a key."
            )
            return

        self._uses_polkit = os.geteuid() != 0
        if self._uses_polkit:
            program = shutil.which("pkexec")
            if program is None:
                self.error_occurred.emit(
                    "pkexec was not found. A Polkit authentication dialog is "
                    "required to read the physical keyboard while keyd is active."
                )
                return
            arguments = [keyd_path, "monitor"]
        else:
            program = keyd_path
            arguments = ["monitor"]

        self._stderr = ""
        self._stdout = ""
        self._process = QProcess(self)
        self._process.errorOccurred.connect(self._on_error)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.start(program, arguments)

    def stop(self) -> None:
        """Stops the keyd monitor process."""
        process = self._process
        if process is None:
            return
        self._process = None
        for signal, slot in (
            (process.errorOccurred, self._on_error),
            (process.readyReadStandardOutput, self._on_output),
            (process.readyReadStandardError, self._on_stderr),
            (process.finished, self._on_finished),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        process.kill()
        process.waitForFinished(200)

    def toggle(self) -> None:
        """Toggles the recording state."""
        if self.is_recording:
            self.stop()
        else:
            self.start()

    def _on_error(self, error: QProcess.ProcessError) -> None:
        """Handles process errors, such as keyd not being installed."""
        if error == QProcess.ProcessError.FailedToStart:
            command = "the Polkit authentication helper" if self._uses_polkit else "keyd"
            message = f"Failed to start {command}."
        else:
            message = "The keyd monitor encountered an unexpected process error."
        self.stop()
        self.error_occurred.emit(message)

    def _on_stderr(self) -> None:
        """Collect diagnostics so permission failures can be explained."""
        if self._process is not None:
            self._stderr += (
                self._process.readAllStandardError().toStdString()
            )

    def _on_finished(
        self,
        exit_code: int,
        _exit_status: QProcess.ExitStatus,
    ) -> None:
        """Report an early monitor exit, most often denied authentication."""
        if self._process is None:
            return
        self._on_stderr()
        details = self._stderr.strip()
        self._process = None
        if exit_code == 0:
            message = "keyd monitor stopped before a key was recorded."
        elif self._uses_polkit and exit_code in {126, 127}:
            message = (
                "Recording permission was denied or authentication was cancelled."
            )
        elif details:
            message = f"keyd monitor failed: {details}"
        else:
            message = f"keyd monitor stopped with exit code {exit_code}."
        self.error_occurred.emit(message)

    def _on_output(self) -> None:
        """Handles output from the keyd monitor process."""
        if self._process is None:
            return
        self._stdout += self._process.readAllStandardOutput().toStdString()
        pattern = re.compile(r"(\w+(?::\w+)+)\s+(\S+)\s+down", re.MULTILINE)
        for match in pattern.finditer(self._stdout):
            full_id, key_name = match.group(1), match.group(2)
            if self._device_id is None or full_id.startswith(self._device_id):
                self.stop()
                self.key_recorded.emit(key_name)
                return
        # Retain enough text for a line split across QProcess output chunks.
        self._stdout = self._stdout[-4096:]
