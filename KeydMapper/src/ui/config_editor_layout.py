"""Integrated physical-layout mode for :mod:`ui.config_editor`."""

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from ui.key_item import KeyItem
from ui.record_button import RecordButton

# This feature mixin is composed into ConfigEditor and shares its editor shell.
# pylint: disable=no-member,too-many-instance-attributes


class PhysicalLayoutMixin:
    """Build and coordinate the physical-keyboard mode in the shared editor."""

    def _build_layout_navigation(self, parent_layout: QVBoxLayout) -> None:
        """Add the persistent Physical layout entry to the layer rail."""
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        parent_layout.addWidget(divider)
        parent_layout.addWidget(QLabel("KEYBOARD"))

        self.keyboard_layout_btn = QPushButton("⌨  Physical layout")
        self.keyboard_layout_btn.setCheckable(True)
        self.keyboard_layout_btn.setEnabled(self._layout_editor is not None)
        self.keyboard_layout_btn.clicked.connect(self._toggle_layout_mode)
        parent_layout.addWidget(self.keyboard_layout_btn)

        device_id = getattr(self.config, "device_id", None)
        self.device_label = QLabel(str(device_id or "Unknown device"))
        self.device_label.setWordWrap(True)
        self.device_label.setStyleSheet("color: #777;")
        parent_layout.addWidget(self.device_label)

    def _build_layout_inspector(self) -> None:
        """Build controls shown instead of Binding while editing geometry."""
        self.layout_inspector = QWidget()
        layout = QVBoxLayout(self.layout_inspector)
        layout.setContentsMargins(6, 6, 6, 6)
        title = QLabel("KEY")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        self.layout_selection_hint = QLabel("Select a key on the keyboard")
        self.layout_selection_hint.setWordWrap(True)
        layout.addWidget(self.layout_selection_hint)
        layout.addWidget(QLabel("Key name:"))

        self.layout_name_input = QLineEdit()
        self.layout_name_input.textEdited.connect(self._apply_layout_key_name)
        layout.addWidget(self.layout_name_input)

        if self._layout_editor is not None:
            self.layout_record_btn = RecordButton(self._layout_editor.recorder)
            self.layout_record_btn.setToolTip(
                "Temporarily pause keyd and capture the next physical key or "
                "mouse button with keyd monitor."
            )
            self._layout_editor.recorder.key_recorded.connect(
                self._on_integrated_key_recorded
            )
        else:
            self.layout_record_btn = QPushButton("Record")
            self.layout_record_btn.setEnabled(False)
        layout.addWidget(self.layout_record_btn)

        self.layout_delete_btn = QPushButton("Delete key")
        self.layout_delete_btn.clicked.connect(self._delete_layout_key)
        self.layout_delete_btn.setEnabled(False)
        layout.addWidget(self.layout_delete_btn)

        actions = QHBoxLayout()
        self.layout_add_btn = QPushButton("Add key")
        self.layout_add_btn.clicked.connect(self._add_layout_key)
        actions.addWidget(self.layout_add_btn)
        self.layout_load_btn = QPushButton("Load layout")
        self.layout_load_btn.clicked.connect(self._choose_layout)
        actions.addWidget(self.layout_load_btn)
        layout.addLayout(actions)
        layout.addStretch()
        layout.addWidget(
            QLabel(
                "Insert: add key · Delete: remove\n"
                "Ctrl+A: select all · Ctrl+C/V: copy/paste\n"
                "Drag: move · Ctrl+drag: snap to grid\n"
                "Scroll: zoom"
            )
        )
        self.inspector_stack.addWidget(self.layout_inspector)

    def activate_mode(self) -> None:
        """Activate whichever integrated editing mode is currently selected."""
        if self._editing_layout and self._layout_editor is not None:
            self._layout_editor.activate_mode()
            self._update_layout_selection()
            return
        self._activate_config_mode()

    def _activate_config_mode(self) -> None:
        """Set up the shared view and items for key binding editing."""
        self._view.disconnect_signals()
        for item in self._scene.items():
            if isinstance(item, KeyItem):
                item.locked = True
        self._refresh_scene_values()
        self._sync_source_editor()

    def _handle_back(self) -> None:
        """Leave layout mode first; otherwise return to configuration selection."""
        if self._editing_layout:
            if self._layout_editor is not None:
                self._layout_editor.reload_saved_layout()
            self._leave_layout_mode()
            return
        self.cancel_requested.emit()

    def _toggle_layout_mode(self, checked: bool) -> None:
        """Enter or finish physical-layout editing from the left navigation."""
        if checked:
            self.enter_layout_mode()
        elif self._editing_layout:
            self._save()

    def enter_layout_mode(self) -> None:
        """Switch the same canvas and inspector into physical-layout editing."""
        if self._layout_editor is None or self._editing_layout:
            return
        self._editing_layout = True
        self.keyboard_layout_btn.blockSignals(True)
        self.keyboard_layout_btn.setChecked(True)
        self.keyboard_layout_btn.blockSignals(False)
        self.layer_list.setEnabled(False)
        self.new_layer_btn.setEnabled(False)
        self.delete_layer_btn.setEnabled(False)
        self.enable_btn.setEnabled(False)
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)
        self.save_apply_btn.setText("Save layout and Done")
        self.save_apply_btn.setEnabled(True)
        self.overall_status.setText("Editing physical layout")
        self.overall_status.setStyleSheet("")
        self.inspector_stack.setCurrentWidget(self.layout_inspector)
        self._layout_editor.activate_mode()
        self._update_layout_selection()

    def _leave_layout_mode(self) -> None:
        """Return to the last active keyd layer without replacing the workspace."""
        if not self._editing_layout:
            return
        if isinstance(self.layout_record_btn, RecordButton):
            self.layout_record_btn.reset()
        self._editing_layout = False
        self.keyboard_layout_btn.blockSignals(True)
        self.keyboard_layout_btn.setChecked(False)
        self.keyboard_layout_btn.blockSignals(False)
        self.layer_list.setEnabled(True)
        self.new_layer_btn.setEnabled(True)
        self.enable_btn.setEnabled(True)
        self.save_apply_btn.setText("Save and Apply")
        self.inspector_stack.setCurrentWidget(self.inspector_splitter)
        self._activate_config_mode()
        self._refresh_layer_widgets(self._current_layer)
        self._update_history_actions()
        self._update_overall_status()
        self._run_keyd_validation()

    def _update_layout_selection(self) -> None:
        """Update the integrated Key inspector from the shared scene selection."""
        key = self.get_selected_key_item()
        self.layout_name_input.blockSignals(True)
        self.layout_name_input.setText(key.key_name if key else "")
        self.layout_name_input.blockSignals(False)
        self.layout_selection_hint.setText(
            f"Selected key: {key.key_name}" if key else "Select a key on the keyboard"
        )
        enabled = key is not None
        self.layout_name_input.setEnabled(enabled)
        self.layout_delete_btn.setEnabled(enabled)
        self.layout_record_btn.setEnabled(enabled)

    def _apply_layout_key_name(self, name: str) -> None:
        """Validate and apply a physical key name in the integrated inspector."""
        if self._layout_editor is None:
            return
        error = self._layout_editor.rename_selected_key(name)
        if error == "invalid":
            self.layout_name_input.setStyleSheet("border: 1px solid orange;")
        elif error == "duplicate":
            self.layout_name_input.setStyleSheet("border: 1px solid red;")
        elif error is None:
            self.layout_name_input.setStyleSheet("")
            self.layout_selection_hint.setText(f"Selected key: {name.strip()}")

    def _on_integrated_key_recorded(self, key_name: str) -> None:
        """Mirror a recorded key into the integrated inspector."""
        if not self._editing_layout:
            return
        self.layout_name_input.setText(key_name)
        self._apply_layout_key_name(key_name)

    def _add_layout_key(self) -> None:
        if self._layout_editor is not None:
            self._layout_editor.add_key()

    def _delete_layout_key(self) -> None:
        if self._layout_editor is not None:
            self._layout_editor.delete_selected_keys()

    def _choose_layout(self) -> None:
        if self._layout_editor is not None:
            self._layout_editor.choose_layout()
