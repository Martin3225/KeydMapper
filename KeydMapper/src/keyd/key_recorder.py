"""Record keyd-compatible logical input from Qt application events."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication


_SPECIAL_KEYS = {
    Qt.Key.Key_Escape: "esc",
    Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_Backtab: "tab",
    Qt.Key.Key_Backspace: "backspace",
    Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Enter: "kpenter",
    Qt.Key.Key_Insert: "insert",
    Qt.Key.Key_Delete: "delete",
    Qt.Key.Key_Pause: "pause",
    Qt.Key.Key_Print: "print",
    Qt.Key.Key_SysReq: "sysrq",
    Qt.Key.Key_Home: "home",
    Qt.Key.Key_End: "end",
    Qt.Key.Key_Left: "left",
    Qt.Key.Key_Up: "up",
    Qt.Key.Key_Right: "right",
    Qt.Key.Key_Down: "down",
    Qt.Key.Key_PageUp: "pageup",
    Qt.Key.Key_PageDown: "pagedown",
    Qt.Key.Key_Shift: "shift",
    Qt.Key.Key_Control: "control",
    Qt.Key.Key_Meta: "meta",
    Qt.Key.Key_Alt: "leftalt",
    Qt.Key.Key_AltGr: "rightalt",
    Qt.Key.Key_CapsLock: "capslock",
    Qt.Key.Key_NumLock: "numlock",
    Qt.Key.Key_ScrollLock: "scrolllock",
    Qt.Key.Key_Space: "space",
    Qt.Key.Key_Minus: "minus",
    Qt.Key.Key_Equal: "equal",
    Qt.Key.Key_BracketLeft: "leftbrace",
    Qt.Key.Key_BracketRight: "rightbrace",
    Qt.Key.Key_Backslash: "backslash",
    Qt.Key.Key_Semicolon: "semicolon",
    Qt.Key.Key_Apostrophe: "apostrophe",
    Qt.Key.Key_QuoteLeft: "grave",
    Qt.Key.Key_Comma: "comma",
    Qt.Key.Key_Period: "dot",
    Qt.Key.Key_Slash: "slash",
    Qt.Key.Key_Exclam: "1",
    Qt.Key.Key_At: "2",
    Qt.Key.Key_NumberSign: "3",
    Qt.Key.Key_Dollar: "4",
    Qt.Key.Key_Percent: "5",
    Qt.Key.Key_AsciiCircum: "6",
    Qt.Key.Key_Ampersand: "7",
    Qt.Key.Key_Asterisk: "8",
    Qt.Key.Key_ParenLeft: "9",
    Qt.Key.Key_ParenRight: "0",
    Qt.Key.Key_Underscore: "minus",
    Qt.Key.Key_Plus: "equal",
    Qt.Key.Key_BraceLeft: "leftbrace",
    Qt.Key.Key_BraceRight: "rightbrace",
    Qt.Key.Key_Bar: "backslash",
    Qt.Key.Key_Colon: "semicolon",
    Qt.Key.Key_QuoteDbl: "apostrophe",
    Qt.Key.Key_AsciiTilde: "grave",
    Qt.Key.Key_Less: "comma",
    Qt.Key.Key_Greater: "dot",
    Qt.Key.Key_Question: "slash",
    Qt.Key.Key_VolumeMute: "mute",
    Qt.Key.Key_VolumeDown: "volumedown",
    Qt.Key.Key_VolumeUp: "volumeup",
    Qt.Key.Key_MediaNext: "nextsong",
    Qt.Key.Key_MediaPrevious: "previoussong",
    Qt.Key.Key_MediaPlay: "playpause",
    Qt.Key.Key_MediaStop: "stopcd",
    Qt.Key.Key_MicMute: "micmute",
    Qt.Key.Key_MonBrightnessDown: "brightnessdown",
    Qt.Key.Key_MonBrightnessUp: "brightnessup",
}

_MOUSE_KEYS = {
    Qt.MouseButton.LeftButton: "leftmouse",
    Qt.MouseButton.MiddleButton: "middlemouse",
    Qt.MouseButton.RightButton: "rightmouse",
    Qt.MouseButton.BackButton: "mouseback",
    Qt.MouseButton.ForwardButton: "mouseforward",
    Qt.MouseButton.TaskButton: "mouse1",
    Qt.MouseButton.ExtraButton4: "mouse2",
}

_MODIFIERS = (
    (Qt.KeyboardModifier.ControlModifier, "C", Qt.Key.Key_Control),
    (Qt.KeyboardModifier.ShiftModifier, "S", Qt.Key.Key_Shift),
    (Qt.KeyboardModifier.AltModifier, "A", Qt.Key.Key_Alt),
    (Qt.KeyboardModifier.MetaModifier, "M", Qt.Key.Key_Meta),
    (Qt.KeyboardModifier.GroupSwitchModifier, "G", Qt.Key.Key_AltGr),
)
_MODIFIER_KEYS = {
    Qt.Key.Key_Shift,
    Qt.Key.Key_Control,
    Qt.Key.Key_Meta,
    Qt.Key.Key_Alt,
    Qt.Key.Key_AltGr,
}

_KEYPAD_KEYS = {
    Qt.Key.Key_0: "kp0",
    Qt.Key.Key_1: "kp1",
    Qt.Key.Key_2: "kp2",
    Qt.Key.Key_3: "kp3",
    Qt.Key.Key_4: "kp4",
    Qt.Key.Key_5: "kp5",
    Qt.Key.Key_6: "kp6",
    Qt.Key.Key_7: "kp7",
    Qt.Key.Key_8: "kp8",
    Qt.Key.Key_9: "kp9",
    Qt.Key.Key_Plus: "kpplus",
    Qt.Key.Key_Minus: "kpminus",
    Qt.Key.Key_Asterisk: "kpasterisk",
    Qt.Key.Key_Slash: "kpslash",
    Qt.Key.Key_Period: "kpdot",
    Qt.Key.Key_Enter: "kpenter",
}


class KeyRecorder(QObject):
    """Capture the next logical key, shortcut, mouse button, or wheel action.

    keyd owns the physical devices while its daemon is active and publishes
    remapped events through virtual input devices. Qt already receives that
    logical stream, so recording it here needs neither root privileges nor a
    fragile physical-to-virtual device-id mapping.
    """

    key_recorded = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        _device_id: str | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._recording = False

    @property
    def is_recording(self) -> bool:
        """Return whether the next supported application input will be captured."""
        return self._recording

    def start(self) -> None:
        """Arm application-wide logical input capture."""
        if self._recording:
            return
        app = QApplication.instance()
        if app is None:
            self.error_occurred.emit("The Qt application is not running.")
            return
        self._recording = True
        app.installEventFilter(self)

    def stop(self) -> None:
        """Disarm capture and remove the application event filter."""
        if not self._recording:
            return
        self._recording = False
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def toggle(self) -> None:
        """Toggle capture of the next logical input."""
        if self.is_recording:
            self.stop()
        else:
            self.start()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Consume and emit the first supported event while armed."""
        _ = watched
        if not self._recording:
            return False

        key_name: str | None = None
        if event.type() == QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QKeyEvent) and not key_event.isAutoRepeat():
                if key_event.key() in _MODIFIER_KEYS:
                    return True
                key_name = self._key_expression(key_event)
        elif event.type() == QEvent.Type.MouseButtonPress:
            mouse_event = event
            if isinstance(mouse_event, QMouseEvent):
                key_name = self._mouse_name(mouse_event.button())
                key_name = self._with_modifiers(
                    key_name,
                    mouse_event.modifiers(),
                )
        elif event.type() == QEvent.Type.Wheel:
            wheel_event = event
            if isinstance(wheel_event, QWheelEvent):
                key_name = self._wheel_name(wheel_event)
                key_name = self._with_modifiers(
                    key_name,
                    wheel_event.modifiers(),
                )

        if key_name is None:
            return False
        self.stop()
        self.key_recorded.emit(key_name)
        return True

    @staticmethod
    def _key_expression(event: QKeyEvent) -> str | None:
        """Translate one Qt key press and its modifiers into keyd syntax."""
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.KeyboardModifier.KeypadModifier:
            base = _KEYPAD_KEYS.get(key)
        elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            base = chr(ord("a") + key - Qt.Key.Key_A)
        elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            base = chr(ord("0") + key - Qt.Key.Key_0)
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F35:
            base = f"f{key - Qt.Key.Key_F1 + 1}"
        else:
            base = _SPECIAL_KEYS.get(key)

        if base is None:
            return None

        return KeyRecorder._with_modifiers(base, modifiers, key)

    @staticmethod
    def _with_modifiers(
        base: str | None,
        modifiers: Qt.KeyboardModifier,
        key: int | None = None,
    ) -> str | None:
        """Prefix a captured action with keyd's active modifier notation."""
        if base is None:
            return None
        group_switch = bool(
            modifiers & Qt.KeyboardModifier.GroupSwitchModifier
        )
        prefixes = [
            prefix
            for modifier, prefix, modifier_key in _MODIFIERS
            if modifiers & modifier
            and key != modifier_key
            and not (
                group_switch
                and modifier
                in {
                    Qt.KeyboardModifier.ControlModifier,
                    Qt.KeyboardModifier.AltModifier,
                }
            )
        ]
        return "-".join((*prefixes, base))

    @staticmethod
    def _mouse_name(button: Qt.MouseButton) -> str | None:
        """Translate standard and additional Qt mouse buttons."""
        return _MOUSE_KEYS.get(button)

    @staticmethod
    def _wheel_name(event: QWheelEvent) -> str | None:
        """Translate the dominant wheel axis into a keyd scroll action."""
        delta = event.angleDelta()
        if abs(delta.y()) >= abs(delta.x()) and delta.y():
            return "scrollup" if delta.y() > 0 else "scrolldown"
        if delta.x():
            return "scrollright" if delta.x() > 0 else "scrollleft"
        return None
