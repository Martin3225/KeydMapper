"""Record physical keyd input without keeping the GUI thread blocked."""

from __future__ import annotations

import threading

from keyd.system_helper import (
    SystemHelperError,
    cancel_key_recording,
    record_key,
)
from PySide6.QtCore import QObject, Signal


class KeyRecorder(QObject):
    """Capture one physical key or shortcut through privileged keyd monitor.

    keyd must release its input devices before the monitor can see their
    original events. The privileged helper pauses the service only for the
    duration of a recording and restores its previous state in every exit path.
    """

    key_recorded = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        device_id: str | None = None,
        *,
        capture_shortcut: bool = True,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._device_id = device_id
        self._capture_shortcut = capture_shortcut
        self._recording = False
        self._cancel_event: threading.Event | None = None
        self._state_lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        """Return whether a physical-input capture is in progress."""
        with self._state_lock:
            return self._recording

    def start(self) -> None:
        """Start one cancellable monitor request on a worker thread."""
        with self._state_lock:
            if self._recording:
                return
            self._recording = True
            cancel_event = threading.Event()
            self._cancel_event = cancel_event

        worker = threading.Thread(
            target=self._record,
            args=(cancel_event,),
            name="keyd-monitor-recorder",
            daemon=True,
        )
        worker.start()

    def stop(self) -> None:
        """Cancel an active monitor request and restore keyd asynchronously."""
        with self._state_lock:
            if not self._recording:
                return
            self._recording = False
            cancel_event = self._cancel_event
        if cancel_event is not None:
            cancel_event.set()
        cancel_key_recording()

    def toggle(self) -> None:
        """Toggle physical-input capture."""
        if self.is_recording:
            self.stop()
        else:
            self.start()

    def _record(self, cancel_event: threading.Event) -> None:
        """Run the blocking helper transaction away from Qt's GUI thread."""
        captured: str | None = None
        error_message: str | None = None
        try:
            captured = record_key(
                self._device_id,
                capture_shortcut=self._capture_shortcut,
                cancel_event=cancel_event,
            )
        except SystemHelperError as error:
            error_message = str(error)

        with self._state_lock:
            is_current = self._cancel_event is cancel_event
            should_emit = (
                is_current
                and self._recording
                and not cancel_event.is_set()
            )
            if is_current:
                self._recording = False
                self._cancel_event = None

        if not should_emit:
            return
        if error_message is not None:
            self.error_occurred.emit(error_message)
        elif captured is not None:
            self.key_recorded.emit(captured)
