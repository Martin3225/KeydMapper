"""Tests for password-free logical input recording."""
# pylint: disable=protected-access

from unittest.mock import MagicMock, patch

from keyd.key_recorder import KeyRecorder
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent


def test_key_recorder_initialization():
    """The recorder starts disarmed and no longer owns a root process."""
    recorder = KeyRecorder("1234:5678")

    assert recorder.is_recording is False
    assert not hasattr(recorder, "_process")


def test_key_recorder_start_stop():
    """Capture is armed and disarmed through QApplication's event filter."""
    recorder = KeyRecorder()

    recorder.start()
    assert recorder.is_recording is True

    recorder.stop()
    assert recorder.is_recording is False


def test_key_recorder_reports_missing_qt_application():
    """Starting outside a Qt application gives a useful error."""
    recorder = KeyRecorder()
    errors = MagicMock()
    recorder.error_occurred.connect(errors)

    with patch("keyd.key_recorder.QApplication.instance", return_value=None):
        recorder.start()

    assert recorder.is_recording is False
    assert "Qt application" in errors.call_args.args[0]


def test_key_recorder_toggle():
    """toggle() switches the logical capture state."""
    recorder = KeyRecorder()

    recorder.toggle()
    assert recorder.is_recording is True

    recorder.toggle()
    assert recorder.is_recording is False


def test_key_recorder_captures_shortcut_and_consumes_event():
    """Qt modifiers are emitted in keyd's compact shortcut syntax."""
    recorder = KeyRecorder()
    recorded = MagicMock()
    recorder.key_recorded.connect(recorded)
    recorder.start()
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.ShiftModifier,
    )

    consumed = recorder.eventFilter(recorder, event)

    assert consumed is True
    assert recorder.is_recording is False
    recorded.assert_called_once_with("C-S-a")


def test_key_recorder_ignores_key_auto_repeat():
    """Holding a key cannot accidentally complete a newly armed capture."""
    recorder = KeyRecorder()
    recorded = MagicMock()
    recorder.key_recorded.connect(recorded)
    recorder.start()
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.NoModifier,
        "",
        True,
        2,
    )

    assert recorder.eventFilter(recorder, event) is False
    assert recorder.is_recording is True
    recorded.assert_not_called()
    recorder.stop()


def test_key_recorder_captures_virtual_mouse_output():
    """Mouse events need no physical id such as the Razer device id."""
    recorder = KeyRecorder("1532:0099")
    recorded = MagicMock()
    recorder.key_recorded.connect(recorded)
    recorder.start()
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    assert recorder.eventFilter(recorder, event) is True
    recorded.assert_called_once_with("leftmouse")


def test_key_recorder_maps_additional_mouse_buttons():
    """Qt back/forward and extra buttons have keyd-compatible names."""
    assert KeyRecorder._mouse_name(Qt.MouseButton.BackButton) == "mouseback"
    assert KeyRecorder._mouse_name(Qt.MouseButton.ForwardButton) == "mouseforward"
    assert KeyRecorder._mouse_name(Qt.MouseButton.TaskButton) == "mouse1"
    assert KeyRecorder._mouse_name(Qt.MouseButton.ExtraButton4) == "mouse2"


def test_key_recorder_captures_wheel_direction():
    """Wheel events become keyd's scroll actions."""
    recorder = KeyRecorder()
    recorded = MagicMock()
    recorder.key_recorded.connect(recorded)
    recorder.start()
    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    assert recorder.eventFilter(recorder, event) is True
    recorded.assert_called_once_with("scrolldown")


def test_key_recorder_maps_keypad_and_function_keys():
    """Non-letter keys retain their distinct keyd names."""
    keypad = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_1,
        Qt.KeyboardModifier.KeypadModifier,
    )
    function = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_F12,
        Qt.KeyboardModifier.NoModifier,
    )

    assert KeyRecorder._key_expression(keypad) == "kp1"
    assert KeyRecorder._key_expression(function) == "f12"


def test_altgr_does_not_duplicate_qt_control_and_alt_flags():
    """Qt's Ctrl+Alt implementation detail is normalized to keyd's G prefix."""
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.GroupSwitchModifier,
    )

    assert KeyRecorder._key_expression(event) == "G-a"
