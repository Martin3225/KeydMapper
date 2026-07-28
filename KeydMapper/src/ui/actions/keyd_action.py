"""Visual editor for keyd's complete binding action set."""

from __future__ import annotations

from typing import TYPE_CHECKING

from keyd.actions import (
    ACTION_BY_NAME,
    ActionField,
    ActionFieldKind,
    action_completions,
    format_action,
    parse_action,
)
from keyd.key_recorder import KeyRecorder
from keyd.key_validator import get_valid_keys
from PySide6.QtCore import Qt, QStringListModel, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from ui.actions.base import ConfigActionWidget
from ui.key_item import KeyItem

if TYPE_CHECKING:
    from ui.config_editor import ConfigEditor

# Qt forms naturally keep references to their child controls.
# pylint: disable=too-many-instance-attributes


DEFAULT_TIMEOUTS = {
    "timeout": 200,
    "idle_timeout": 1000,
    "hold_timeout": 200,
    "repeat_timeout": 50,
}


class KeydActionEditor(ConfigActionWidget):
    """Edit every keyd action without exposing internal ``*m`` variants."""

    def __init__(self, editor: "ConfigEditor"):
        super().__init__(editor)
        self._loading = False
        self._current_action_name = next(iter(ACTION_BY_NAME))
        self._field_widgets: dict[str, QWidget] = {}
        self._record_buttons: dict[
            QPushButton,
            tuple[QLineEdit, ActionFieldKind],
        ] = {}
        self._dynamic_record_buttons: list[QPushButton] = []
        self._record_target: tuple[
            QLineEdit,
            ActionFieldKind,
            QPushButton,
        ] | None = None
        self._recorder = KeyRecorder(
            getattr(editor.config, "device_id", None),
            capture_shortcut=True,
            parent=self,
        )
        self._recorder.key_recorded.connect(self._on_recorded_input)
        self._recorder.error_occurred.connect(self._on_recording_error)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._description = QLabel()
        self._description.setWordWrap(True)
        self._description.setStyleSheet("color: #777;")
        layout.addWidget(self._description)

        self._fields_container = QWidget()
        self._fields_layout = QFormLayout(self._fields_container)
        self._fields_layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self._fields_container)

        self._macro_checkbox = QCheckBox("Also run a macro")
        self._macro_checkbox.toggled.connect(self._on_macro_toggled)
        layout.addWidget(self._macro_checkbox)

        self._macro_input = QLineEdit()
        self._macro_input.setPlaceholderText("macro(C-a C-c)")
        self._macro_input.setToolTip(
            "Runs in parallel with the action. The generated config uses "
            "keyd's matching macro-capable form automatically."
        )
        self._macro_input.textEdited.connect(self._apply)
        self._macro_input_container = self._with_record_button(
            self._macro_input,
            ActionFieldKind.MACRO_EXPRESSION,
        )
        layout.addWidget(self._macro_input_container)

        self._held_key_checkbox = QCheckBox("Act as a key while held")
        self._held_key_checkbox.toggled.connect(self._on_held_key_toggled)
        layout.addWidget(self._held_key_checkbox)

        self._held_key_input = QLineEdit()
        self._held_key_input.setPlaceholderText("a")
        self._held_key_input.textEdited.connect(self._apply)
        self._held_key_input_container = self._with_record_button(
            self._held_key_input,
            ActionFieldKind.ACTION_EXPRESSION,
        )
        layout.addWidget(self._held_key_input_container)

        self._reset_button = QPushButton("Reset binding")
        self._reset_button.clicked.connect(self._reset)
        layout.addWidget(self._reset_button)

        self._rebuild_fields()
        self.on_selection_changed(None)

    @property
    def current_action_name(self) -> str:
        """Return the normalized keyd action selected in the form."""
        return self._current_action_name

    def on_selection_changed(self, key_item: KeyItem | None) -> None:
        """Load a selected binding without writing anything back."""
        self._loading = True
        try:
            self.setEnabled(key_item is not None)
            self._reset_button.setEnabled(
                key_item is not None and bool(key_item.key_value)
            )
            if key_item is None:
                self._clear_form()
                return

            parsed = parse_action(key_item.key_value)
            if parsed is None:
                self._clear_form()
                return

            self._current_action_name = parsed.action_name
            self._rebuild_fields()
            spec = ACTION_BY_NAME[parsed.action_name]
            for field, value in zip(spec.fields, parsed.arguments):
                self._set_field_value(field, value)
            self._macro_checkbox.setChecked(bool(parsed.macro))
            self._macro_input.setText(parsed.macro)
            self._held_key_checkbox.setChecked(bool(parsed.held_key))
            self._held_key_input.setText(parsed.held_key)
            self._update_additional_controls()
        finally:
            self._loading = False

    def on_layer_changed(self, layer: str) -> None:
        """Refresh layer choices after the configuration structure changes."""
        _ = layer
        self.on_selection_changed(self.editor.get_selected_key_item())

    def select_action(self, action_name: str) -> None:
        """Switch the form to an action chosen by the shared Binding dropdown."""
        if action_name not in ACTION_BY_NAME:
            raise ValueError(f"Unknown keyd action: {action_name}")
        if self._loading:
            return
        key_item = self.editor.get_selected_key_item()
        self.setEnabled(key_item is not None)
        self._reset_button.setEnabled(
            key_item is not None and bool(key_item.key_value)
        )
        self._loading = True
        try:
            self._current_action_name = action_name
            self._rebuild_fields()
            self._macro_checkbox.setChecked(False)
            self._macro_input.clear()
            self._held_key_checkbox.setChecked(False)
            self._held_key_input.clear()
            self._update_additional_controls()
        finally:
            self._loading = False
        self._apply()

    def _rebuild_fields(self) -> None:
        """Build controls from the shared action specification."""
        self._stop_recording()
        for button in self._dynamic_record_buttons:
            self._record_buttons.pop(button, None)
        self._dynamic_record_buttons.clear()
        while self._fields_layout.rowCount():
            self._fields_layout.removeRow(0)
        self._field_widgets.clear()

        spec = ACTION_BY_NAME[self.current_action_name]
        self._description.setText(spec.help_text)
        for field in spec.fields:
            widget = self._create_field_widget(field)
            self._field_widgets[field.argument_id] = widget
            row_widget: QWidget = widget
            if isinstance(widget, QLineEdit) and field.input_kind in {
                ActionFieldKind.KEY_SEQUENCE,
                ActionFieldKind.ACTION_EXPRESSION,
                ActionFieldKind.MACRO_BODY,
                ActionFieldKind.MACRO_EXPRESSION,
            }:
                row_widget = self._with_record_button(
                    widget,
                    field.input_kind,
                    dynamic=True,
                )
            self._fields_layout.addRow(f"{field.label}:", row_widget)
        self._update_additional_controls()

    def _with_record_button(
        self,
        line_edit: QLineEdit,
        input_kind: ActionFieldKind,
        *,
        dynamic: bool = False,
    ) -> QWidget:
        """Place one line edit beside a button backed by the shared recorder."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(line_edit, stretch=1)

        button = QPushButton("Record")
        button.setToolTip(
            "Temporarily pause keyd and insert physical input from keyd monitor."
        )
        button.clicked.connect(
            lambda checked=False, target=line_edit, kind=input_kind, control=button:
            self._toggle_recording(target, kind, control)
        )
        row.addWidget(button)
        self._record_buttons[button] = (line_edit, input_kind)
        if dynamic:
            self._dynamic_record_buttons.append(button)
        return container

    def _toggle_recording(
        self,
        target: QLineEdit,
        input_kind: ActionFieldKind,
        button: QPushButton,
    ) -> None:
        """Start one field-targeted capture or cancel the active capture."""
        if self._recorder.is_recording:
            self._stop_recording()
            return
        self._record_target = (target, input_kind, button)
        self._recorder.start()
        self._update_record_buttons()

    def _stop_recording(self) -> None:
        self._recorder.stop()
        self._record_target = None
        self._update_record_buttons()

    def _update_record_buttons(self) -> None:
        active_button = (
            self._record_target[2]
            if self._recorder.is_recording and self._record_target
            else None
        )
        for button in self._record_buttons:
            button.setText("◼ Stop" if button is active_button else "Record")
            button.setEnabled(active_button is None or button is active_button)

    @staticmethod
    def _append_recorded_value(
        current: str,
        recorded: str,
        input_kind: ActionFieldKind,
    ) -> str:
        """Insert a captured shortcut in the syntax expected by one field."""
        current = current.strip()
        if input_kind is ActionFieldKind.MACRO_BODY:
            return " ".join(part for part in (current, recorded) if part)
        if input_kind is ActionFieldKind.MACRO_EXPRESSION:
            if not current:
                return f"macro({recorded})"
            if current.startswith("macro(") and current.endswith(")"):
                body = current[6:-1].strip()
                body = " ".join(part for part in (body, recorded) if part)
                return f"macro({body})"
        return recorded

    def _on_recorded_input(self, recorded: str) -> None:
        """Insert one captured key into the field that started recording."""
        target = self._record_target
        self._record_target = None
        self._update_record_buttons()
        if target is None:
            return
        line_edit, input_kind, _ = target
        line_edit.setText(
            self._append_recorded_value(
                line_edit.text(),
                recorded,
                input_kind,
            )
        )
        self._apply()

    def _on_recording_error(self, message: str) -> None:
        """Show one error for the shared recorder and reset every field button."""
        self._record_target = None
        self._update_record_buttons()
        QMessageBox.warning(self, "Recording Error", message)

    def _create_field_widget(self, field: ActionField) -> QWidget:
        """Create the appropriate control for one action argument."""
        if field.input_kind is ActionFieldKind.LAYER_NAME:
            widget = QComboBox()
            widget.setEditable(True)
            for layer_name in self.editor.config.layer_order:
                base_name = layer_name.split(":", 1)[0]
                if widget.findText(base_name) < 0:
                    widget.addItem(base_name)
            widget.setCurrentIndex(-1)
            widget.setPlaceholderText(field.example)
            widget.currentTextChanged.connect(self._apply)
            return widget

        if field.input_kind is ActionFieldKind.TIMEOUT_MS:
            widget = QSpinBox()
            widget.setRange(0, 2_147_483_647)
            widget.setSuffix(" ms")
            widget.setValue(DEFAULT_TIMEOUTS.get(field.argument_id, 0))
            widget.valueChanged.connect(self._apply)
            return widget

        widget = QLineEdit()
        widget.setPlaceholderText(field.example)
        widget.textEdited.connect(self._apply)
        if field.input_kind in {
            ActionFieldKind.KEY_SEQUENCE,
            ActionFieldKind.ACTION_EXPRESSION,
        }:
            self._add_keyd_completer(widget)
        return widget

    def _add_keyd_completer(self, widget: QLineEdit) -> None:
        """Offer nested key/action examples without constraining free-form input."""
        values = sorted(set(get_valid_keys()) | set(action_completions()))
        completer = QCompleter(QStringListModel(values, widget), widget)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.activated.connect(
            lambda _completion: QTimer.singleShot(0, self._apply)
        )
        widget.setCompleter(completer)

    def _on_macro_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        if checked and self._held_key_checkbox.isChecked():
            self._held_key_checkbox.setChecked(False)
        self._update_additional_controls()
        self._apply()

    def _on_held_key_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        if checked and self._macro_checkbox.isChecked():
            self._macro_checkbox.setChecked(False)
        self._update_additional_controls()
        self._apply()

    def _update_additional_controls(self) -> None:
        spec = ACTION_BY_NAME[self.current_action_name]
        supports_macro = spec.macro_function is not None
        self._macro_checkbox.setVisible(supports_macro)
        self._macro_input_container.setVisible(
            supports_macro and self._macro_checkbox.isChecked()
        )
        supports_held_key = spec.held_key_function is not None
        self._held_key_checkbox.setVisible(supports_held_key)
        self._held_key_input_container.setVisible(
            supports_held_key and self._held_key_checkbox.isChecked()
        )

    def _clear_form(self) -> None:
        """Clear stale values when the binding is literal or absent."""
        for field in ACTION_BY_NAME[self.current_action_name].fields:
            self._set_field_value(field, "")
        self._macro_checkbox.setChecked(False)
        self._macro_input.clear()
        self._held_key_checkbox.setChecked(False)
        self._held_key_input.clear()
        self._update_additional_controls()

    def _set_field_value(self, field: ActionField, value: str) -> None:
        widget = self._field_widgets[field.argument_id]
        if isinstance(widget, QSpinBox):
            widget.setValue(int(value) if value.isdigit() else 0)
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(value)
        elif isinstance(widget, QLineEdit):
            widget.setText(value)

    def _field_value(self, field: ActionField) -> str:
        widget = self._field_widgets[field.argument_id]
        if isinstance(widget, QSpinBox):
            return str(widget.value())
        if isinstance(widget, QComboBox):
            return widget.currentText().strip()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        return ""

    def _apply(self, _value: object = None) -> None:
        """Generate and apply the complete action once required fields exist."""
        if self._loading:
            return
        key_item = self.editor.get_selected_key_item()
        if key_item is None:
            return

        spec = ACTION_BY_NAME[self.current_action_name]
        arguments = tuple(self._field_value(field) for field in spec.fields)
        missing = any(not value for value in arguments)
        macro = self._macro_input.text().strip()
        held_key = self._held_key_input.text().strip()
        if self._macro_checkbox.isChecked() and not macro:
            missing = True
        if self._held_key_checkbox.isChecked() and not held_key:
            missing = True
        if missing:
            return

        value = format_action(
            spec.keyd_function,
            arguments,
            macro=macro if self._macro_checkbox.isChecked() else "",
            held_key=(
                held_key if self._held_key_checkbox.isChecked() else ""
            ),
        )
        self.editor.set_key_mapping(key_item, value)
        self._reset_button.setEnabled(True)

    def _reset(self) -> None:
        key_item = self.editor.get_selected_key_item()
        if key_item is not None:
            self.editor.set_key_mapping(key_item, "")
            self.on_selection_changed(key_item)

    # pylint: disable=invalid-name
    def hideEvent(self, event) -> None:
        """Stop monitoring when the action form is no longer visible."""
        self._stop_recording()
        super().hideEvent(event)

    def shutdown(self) -> None:
        """Stop the shared physical-input recorder before editor teardown."""
        self._stop_recording()
