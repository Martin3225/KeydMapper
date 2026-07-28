"""Action widget for setting literal key mapping values."""

from typing import TYPE_CHECKING

from keyd.key_recorder import KeyRecorder
from keyd.key_validator import get_valid_keys, is_valid_value
from PySide6.QtCore import QModelIndex, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QCompleter,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)
from ui.actions.base import ConfigActionWidget
from ui.key_item import KeyItem
from ui.record_button import RecordButton

if TYPE_CHECKING:
    from ui.config_editor import ConfigEditor


class KeyValueCompleter(QCompleter):
    """Complete only the base key while preserving shortcut modifiers."""

    def splitPath(self, path: str) -> list[str]:  # pylint: disable=invalid-name
        """Use the text after the last modifier separator as the query."""
        return [path.rsplit("-", 1)[-1]]

    def pathFromIndex(  # pylint: disable=invalid-name
        self,
        index: QModelIndex,
    ) -> str:
        """Put the completed base key back behind any typed modifiers."""
        completion = super().pathFromIndex(index)
        line_edit = self.widget()
        if not isinstance(line_edit, QLineEdit):
            return completion
        current = line_edit.text()
        prefix, separator, _ = current.rpartition("-")
        return f"{prefix}{separator}{completion}" if separator else completion


def load_key_categories() -> dict[str, list[str]]:
    """Loads and categorizes keys from keyd."""
    categories = {
        "Letters": [],
        "Numbers": [],
        "Function Keys": [],
        "Numpad": [],
        "Modifiers": [],
        "Media": [],
        "Mouse": [],
        "Navigation": [],
        "Symbols": [],
        "Other": [],
    }

    nav_keys = {
        "backspace",
        "delete",
        "down",
        "end",
        "enter",
        "esc",
        "escape",
        "home",
        "insert",
        "left",
        "pagedown",
        "pageup",
        "right",
        "space",
        "tab",
        "up",
    }
    sym_names = {
        "apostrophe",
        "backslash",
        "comma",
        "dot",
        "equal",
        "grave",
        "leftbrace",
        "minus",
        "rightbrace",
        "semicolon",
        "slash",
        "zenkakuhankaku",
    }
    modifier_keywords = (
        "alt",
        "compose",
        "control",
        "level3",
        "meta",
        "shift",
        "super",
    )
    media_keywords = (
        "eject",
        "media",
        "micmute",
        "mute",
        "next",
        "pause",
        "play",
        "prev",
        "sound",
        "stop",
        "volume",
    )

    for key in sorted(list(get_valid_keys())):
        k = key.lower()

        match k:
            case _ if len(k) == 1 and k.isalpha():
                categories["Letters"].append(key)
            case _ if len(k) == 1 and k.isdigit():
                categories["Numbers"].append(key)
            case _ if len(k) == 1 and not k.isalnum():
                categories["Symbols"].append(key)
            case _ if k.startswith("f") and k[1:].isdigit():
                categories["Function Keys"].append(key)
            case _ if k.startswith("kp"):
                categories["Numpad"].append(key)
            case _ if any(mod in k for mod in modifier_keywords):
                categories["Modifiers"].append(key)
            case _ if any(med in k for med in media_keywords):
                categories["Media"].append(key)
            case _ if "mouse" in k:
                categories["Mouse"].append(key)
            case _ if k in nav_keys:
                categories["Navigation"].append(key)
            case _ if k in sym_names:
                categories["Symbols"].append(key)
            case _:
                categories["Other"].append(key)

    return categories


class SetValueAction(ConfigActionWidget):
    """Action to set a literal key value (e.g., 'a', 'control', 'layer(nav)')."""

    def __init__(self, editor: "ConfigEditor"):
        super().__init__(editor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)

        self._value_input = QLineEdit()
        self._value_input.textEdited.connect(self._apply_key_value)
        self._key_completer = KeyValueCompleter(
            sorted(get_valid_keys()),
            self._value_input,
        )
        self._key_completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self._key_completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        self._key_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self._key_completer.activated.connect(
            lambda _completion: QTimer.singleShot(
                0,
                self._apply_key_value,
            )
        )
        self._value_input.setCompleter(self._key_completer)
        input_layout.addWidget(self._value_input)

        self._menu_btn = QToolButton()
        self._menu_btn.setText("...")
        self._menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._setup_key_menu()
        input_layout.addWidget(self._menu_btn)

        layout.addLayout(input_layout)

        # Modifiers row
        mod_layout = QHBoxLayout()
        mod_layout.setContentsMargins(0, 5, 0, 0)
        self._mod_checkboxes: dict[str, QCheckBox] = {}

        modifiers = {"C": "Ctrl", "S": "Shift", "A": "Alt", "M": "Meta", "G": "AltGr"}

        for mod, label in modifiers.items():
            cb = QCheckBox(label)
            cb.setToolTip(f"{mod}-")
            cb.stateChanged.connect(self._update_text_from_checkboxes)
            self._mod_checkboxes[mod] = cb
            mod_layout.addWidget(cb)

        layout.addLayout(mod_layout)

        self._recorder = KeyRecorder(
            getattr(editor.config, "device_id", None),
            capture_shortcut=True,
            parent=self,
        )
        self._recorder.key_recorded.connect(self.on_key_recorded)

        self._record_btn = RecordButton(self._recorder)
        self._record_btn.setToolTip(
            "Temporarily pause keyd and capture the next physical key or "
            "shortcut with keyd monitor."
        )
        layout.addWidget(self._record_btn)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setEnabled(False)
        self._reset_btn.clicked.connect(self._reset_key_value)
        layout.addWidget(self._reset_btn)

    def _setup_key_menu(self) -> None:
        """Sets up the menu with categorized keyd keys."""
        menu = QMenu(self)
        categories = load_key_categories()

        for category_name, keys in categories.items():
            category_menu = menu.addMenu(category_name)
            for key in keys:
                action = category_menu.addAction(key)
                action.triggered.connect(
                    lambda checked, k=key: self._set_key_from_menu(k)
                )

        self._menu_btn.setMenu(menu)

    def _set_key_from_menu(self, key_name: str) -> None:
        """Sets the input value from the menu selection."""
        self._value_input.setText(key_name)
        self._apply_key_value()

    def on_selection_changed(self, key_item: KeyItem | None) -> None:
        """Updates the UI when the selected key changes."""
        if key_item:
            self._value_input.setText(key_item.key_value)
            self._update_checkboxes_from_text(key_item.key_value)
            self._record_btn.setEnabled(True)
            self._reset_btn.setEnabled(True)
        else:
            self._value_input.clear()
            self._update_checkboxes_from_text("")
            self._record_btn.setEnabled(False)
            self._reset_btn.setEnabled(False)
            self._record_btn.reset()

    # Qt framwork invalid methods names
    # pylint: disable=invalid-name
    def hideEvent(self, event) -> None:
        """Called when the widget is hidden; ensures recording is stopped."""
        self._record_btn.reset()
        super().hideEvent(event)

    def _apply_key_value(self, text: str = "") -> None:
        """Applies the current input value to the selected key."""
        _ = text  # read directly from input
        val = self._value_input.text().strip()

        key = self.editor.get_selected_key_item()
        if not key:
            return

        if not is_valid_value(val):
            self._value_input.setStyleSheet("border: 2px solid orange;")
        else:
            self._value_input.setStyleSheet("")

        self._update_checkboxes_from_text(val)

        self.editor.set_key_mapping(key, val)

    def _update_checkboxes_from_text(self, text: str) -> None:
        """Parses the current text and checks corresponding modifier checkboxes."""
        parts = text.split("-")
        modifiers = parts[:-1]

        for cb in self._mod_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)

        for mod in modifiers:
            if mod in self._mod_checkboxes:
                self._mod_checkboxes[mod].setChecked(True)

        for cb in self._mod_checkboxes.values():
            cb.blockSignals(False)

    def _update_text_from_checkboxes(self) -> None:
        """Reconstructs the text based on checked modifiers."""
        current_text = self._value_input.text().strip()
        parts = current_text.split("-")
        base_key = parts[-1] if current_text else ""

        active_mods = []
        for mod, cb in self._mod_checkboxes.items():
            if cb.isChecked():
                active_mods.append(mod)

        new_text = "-".join(active_mods)
        if active_mods:
            new_text += "-" + base_key
        else:
            new_text = base_key

        self._value_input.setText(new_text)
        self._apply_key_value()

    def on_key_recorded(self, key_name: str) -> None:
        """Apply a physical keyd-compatible input captured by keyd monitor."""
        self._value_input.setText(key_name)
        self._apply_key_value()

    def _reset_key_value(self) -> None:
        """Resets the key mapping to an empty value."""
        self._value_input.setText("")
        self._apply_key_value()

    def shutdown(self) -> None:
        """Remove application-wide input capture before editor teardown."""
        self._record_btn.reset()
