"""Tests for asynchronous physical input recording."""
# pylint: disable=protected-access

import threading
import time
from unittest.mock import MagicMock, patch

from keyd.key_recorder import KeyRecorder
from keyd.system_helper import SystemHelperError
from PySide6.QtWidgets import QApplication


def _wait_until(predicate, timeout: float = 1) -> None:
    """Process queued Qt signals until a worker-side condition becomes true."""
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)
    assert predicate()


def test_key_recorder_initialization() -> None:
    """The recorder starts disarmed and stores its monitor options."""
    recorder = KeyRecorder("1234:5678", capture_shortcut=False)

    assert recorder.is_recording is False
    assert recorder._device_id == "1234:5678"
    assert recorder._capture_shortcut is False


def test_key_recorder_captures_on_worker_without_blocking_ui() -> None:
    """A helper result is delivered and disarms the recorder."""
    release = threading.Event()

    def fake_record(*_args, **_kwargs) -> str:
        release.wait(timeout=1)
        return "C-S-a"

    recorder = KeyRecorder("1234:5678", capture_shortcut=True)
    recorded = MagicMock()
    recorder.key_recorded.connect(recorded)

    with patch("keyd.key_recorder.record_key", side_effect=fake_record) as record:
        recorder.start()
        assert recorder.is_recording is True
        release.set()
        _wait_until(lambda: recorded.call_count == 1)

    record.assert_called_once()
    assert record.call_args.args[0] == "1234:5678"
    assert record.call_args.kwargs["capture_shortcut"] is True
    recorded.assert_called_once_with("C-S-a")


def test_key_recorder_stop_cancels_privileged_monitor() -> None:
    """Stopping signals both the worker and the helper protocol."""
    worker_started = threading.Event()
    worker_finished = threading.Event()

    def fake_record(
        _device_id,
        *,
        capture_shortcut,
        cancel_event,
    ) -> None:
        assert capture_shortcut is True
        worker_started.set()
        cancel_event.wait(timeout=1)
        worker_finished.set()

    recorder = KeyRecorder()
    with (
        patch("keyd.key_recorder.record_key", side_effect=fake_record),
        patch("keyd.key_recorder.cancel_key_recording") as cancel,
    ):
        recorder.start()
        assert worker_started.wait(timeout=1)
        recorder.stop()

    assert recorder.is_recording is False
    assert worker_finished.wait(timeout=1)
    cancel.assert_called_once()


def test_key_recorder_reports_helper_error() -> None:
    """Privilege, monitor, and service errors reach the existing UI signal."""
    recorder = KeyRecorder()
    errors = MagicMock()
    recorder.error_occurred.connect(errors)

    with patch(
        "keyd.key_recorder.record_key",
        side_effect=SystemHelperError("monitor unavailable"),
    ):
        recorder.start()
        _wait_until(lambda: errors.call_count == 1)

    errors.assert_called_once_with("monitor unavailable")


def test_key_recorder_toggle() -> None:
    """toggle() starts and cancels the physical capture."""
    blocker = threading.Event()

    def fake_record(*_args, **kwargs):
        kwargs["cancel_event"].wait(timeout=1)
        blocker.set()

    recorder = KeyRecorder()
    with (
        patch("keyd.key_recorder.record_key", side_effect=fake_record),
        patch("keyd.key_recorder.cancel_key_recording"),
    ):
        recorder.toggle()
        assert recorder.is_recording is True
        recorder.toggle()
        assert recorder.is_recording is False

    assert blocker.wait(timeout=1)
