"""Integrated visual editor for keyd bindings and physical keyboard layouts."""

from typing import TYPE_CHECKING, cast

from keyd.config import Config, ConfigSaveError
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsScene,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from ui.actions.base import ConfigActionWidget
from ui.actions.change_layer import ChangeLayerAction
from ui.actions.set_value import SetValueAction
from ui.base_editor import BaseEditor
from ui.config_source_editor import KeydSourceEditor
from ui.context import EditorContext
from ui.key_item import KeyItem
from ui.layout_view import LayoutView
from ui.record_button import RecordButton

if TYPE_CHECKING:
    from ui.layout_editor import LayoutEditor


# @generated [partially] Gemini 3.1: Graphics and styling adjustments
# Number of attributes is high due to the UI layout
# pylint: disable=too-many-instance-attributes,too-many-statements
class ConfigEditor(BaseEditor):
    """Editor mode for modifying key mappings within a keyd configuration."""

    def __init__(
        self,
        config: Config,
        scene: QGraphicsScene,
        view: LayoutView,
        layout_editor: "LayoutEditor | None" = None,
    ):
        context = EditorContext(scene=scene, view=view)
        super().__init__(
            context=context,
        )
        self.config = config
        self._layout_editor = layout_editor
        self._editing_layout = False
        self._has_live_source = isinstance(
            getattr(self.config, "source_text", None), str
        )
        self._history_guard = False
        self._pending_source_text: str | None = None
        self._history: list[str] = []
        self._history_index = -1
        self._saved_source = ""
        self._history_timer = QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.setInterval(350)
        self._history_timer.timeout.connect(self._commit_source_history)
        self._validation_timer = QTimer(self)
        self._validation_timer.setSingleShot(True)
        self._validation_timer.setInterval(300)
        self._validation_timer.timeout.connect(self._run_keyd_validation)
        self.save_requested.connect(self._save)
        self._current_layer = "main"

        # Toolbar
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._handle_back)
        self.toolbar_layout.addWidget(self.back_btn)

        self.config_name_label = QLabel(f"{self.config.name}")
        self.config_name_label.setStyleSheet("font-weight: bold; margin-right: 5px;")
        self.toolbar_layout.addWidget(self.config_name_label)

        self.enable_btn = QPushButton()
        self.enable_btn.clicked.connect(self.set_config_enabled)
        self.toolbar_layout.addWidget(self.enable_btn)
        self._update_enable_button()

        self.toolbar_layout.addSpacing(20)
        self.toolbar_layout.addStretch()

        # Retained as an internal compatibility adapter for action widgets.
        self.layer_combo = QComboBox(self)
        self.layer_combo.addItems(self.config.layer_order)
        self.layer_combo.currentTextChanged.connect(self._on_layer_changed)
        self.layer_combo.hide()

        self.overall_status = QLabel()
        self.toolbar_layout.addWidget(self.overall_status)

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undo_config_change)
        self.toolbar_layout.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("Redo")
        self.redo_btn.clicked.connect(self.redo_config_change)
        self.toolbar_layout.addWidget(self.redo_btn)

        self.save_apply_btn = QPushButton("Save and Apply")
        self.save_apply_btn.clicked.connect(self._save)
        self.toolbar_layout.addWidget(self.save_apply_btn)

        # Config mode uses the top command bar instead of duplicate bottom buttons.
        self.cancel_btn.hide()
        self.save_btn.hide()

        # Left layer rail.
        self.layer_panel = QFrame()
        self.layer_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.layer_panel.setMinimumWidth(0)
        self.layer_panel.setMaximumWidth(16777215)
        layer_panel_layout = QVBoxLayout(self.layer_panel)
        layer_panel_layout.addWidget(QLabel("LAYERS"))

        self.layer_list = QListWidget()
        self.layer_list.addItems(self.config.layer_order)
        self.layer_list.currentTextChanged.connect(self._on_layer_list_changed)
        layer_panel_layout.addWidget(self.layer_list, stretch=1)

        layer_buttons = QHBoxLayout()
        self.new_layer_btn = QPushButton("+ Layer")
        self.new_layer_btn.clicked.connect(self._create_new_layer)
        layer_buttons.addWidget(self.new_layer_btn)

        self.delete_layer_btn = QPushButton("Delete")
        self.delete_layer_btn.clicked.connect(self._delete_current_layer)
        self.delete_layer_btn.setEnabled(False)
        layer_buttons.addWidget(self.delete_layer_btn)
        layer_panel_layout.addLayout(layer_buttons)

        layer_divider = QFrame()
        layer_divider.setFrameShape(QFrame.Shape.HLine)
        layer_panel_layout.addWidget(layer_divider)
        layer_panel_layout.addWidget(QLabel("KEYBOARD"))

        self.keyboard_layout_btn = QPushButton("⌨  Physical layout")
        self.keyboard_layout_btn.setCheckable(True)
        self.keyboard_layout_btn.setEnabled(self._layout_editor is not None)
        self.keyboard_layout_btn.clicked.connect(self._toggle_layout_mode)
        layer_panel_layout.addWidget(self.keyboard_layout_btn)

        device_id = getattr(self.config, "device_id", None)
        self.device_label = QLabel(str(device_id or "Unknown device"))
        self.device_label.setWordWrap(True)
        self.device_label.setStyleSheet("color: #777;")
        layer_panel_layout.addWidget(self.device_label)

        self._splitter.insertWidget(0, self.layer_panel)
        self._splitter.setChildrenCollapsible(True)

        # Right inspector: binding controls and generated config are simultaneous.
        self.side_panel.setMinimumWidth(0)
        self.side_panel.setMaximumWidth(16777215)
        self.inspector_stack = QStackedWidget()
        self.panel_layout.addWidget(self.inspector_stack)

        self.inspector_splitter = QSplitter(Qt.Orientation.Vertical)
        self.inspector_splitter.setChildrenCollapsible(True)
        self.inspector_stack.addWidget(self.inspector_splitter)

        self.actions_page = QWidget()
        actions_layout = QVBoxLayout(self.actions_page)
        actions_layout.setContentsMargins(6, 6, 6, 6)
        inspector_title = QLabel("BINDING")
        inspector_title.setStyleSheet("font-weight: bold;")
        actions_layout.addWidget(inspector_title)
        self.selection_hint = QLabel("Select a key on the keyboard")
        self.selection_hint.setWordWrap(True)
        actions_layout.addWidget(self.selection_hint)
        actions_layout.addWidget(QLabel("Action:"))

        self._action_selector = QComboBox()
        self._action_selector.addItems(["Set key value", "Change layer"])
        self._action_selector.currentIndexChanged.connect(self._on_action_mode_changed)
        actions_layout.addWidget(self._action_selector)

        self._action_stack = QStackedWidget()
        self.set_value_action = SetValueAction(self)
        self.change_layer_action = ChangeLayerAction(self)

        self._action_stack.addWidget(self.set_value_action)
        self._action_stack.addWidget(self.change_layer_action)
        actions_layout.addWidget(self._action_stack)
        actions_layout.addStretch()
        self.inspector_splitter.addWidget(self.actions_page)

        self.config_panel = QWidget()
        source_layout = QVBoxLayout(self.config_panel)
        source_layout.setContentsMargins(6, 6, 6, 6)

        self.source_header_widget = QWidget()
        source_header = QHBoxLayout(self.source_header_widget)
        source_header.setContentsMargins(0, 0, 0, 0)
        source_title = QLabel("GENERATED CONFIG")
        source_title.setStyleSheet("font-weight: bold;")
        source_header.addWidget(source_title)
        source_header.addStretch()

        self.edit_source_btn = QToolButton()
        self.edit_source_btn.setText("Edit config")
        self.edit_source_btn.setCheckable(True)
        self.edit_source_btn.toggled.connect(self._set_source_editing)
        source_header.addWidget(self.edit_source_btn)

        self.expand_source_btn = QToolButton()
        self.expand_source_btn.setText("Expand")
        self.expand_source_btn.setCheckable(True)
        self.expand_source_btn.toggled.connect(self._set_source_expanded)
        source_header.addWidget(self.expand_source_btn)

        self.toggle_source_btn = QToolButton()
        self.toggle_source_btn.clicked.connect(self._toggle_source_preview)
        source_header.addWidget(self.toggle_source_btn)
        source_layout.addWidget(self.source_header_widget)

        self.source_status = QLabel()
        self.source_status.setWordWrap(True)

        self.source_editor = KeydSourceEditor()
        self.source_editor.setReadOnly(True)
        self.source_editor.setToolTip(
            "Live keyd configuration source. Press Ctrl+Space for suggestions."
        )
        if self._has_live_source:
            self.source_editor.setPlainText(self.config.source())
            self.source_editor.set_completion_layers(self.config.layer_order)
            self._update_source_status()
        self.source_editor.textChanged.connect(self._on_source_text_changed)
        source_layout.addWidget(self.source_editor, stretch=1)
        source_layout.addWidget(self.source_status)

        self.inspector_splitter.addWidget(self.config_panel)
        self.inspector_splitter.setStretchFactor(0, 2)
        self.inspector_splitter.setStretchFactor(1, 3)
        self.inspector_splitter.setSizes([260, 390])

        # Integrated physical-layout inspector.
        self.layout_inspector = QWidget()
        layout_inspector_layout = QVBoxLayout(self.layout_inspector)
        layout_inspector_layout.setContentsMargins(6, 6, 6, 6)
        layout_title = QLabel("KEY")
        layout_title.setStyleSheet("font-weight: bold;")
        layout_inspector_layout.addWidget(layout_title)

        self.layout_selection_hint = QLabel("Select a key on the keyboard")
        self.layout_selection_hint.setWordWrap(True)
        layout_inspector_layout.addWidget(self.layout_selection_hint)
        layout_inspector_layout.addWidget(QLabel("Key name:"))

        self.layout_name_input = QLineEdit()
        self.layout_name_input.textEdited.connect(self._apply_layout_key_name)
        layout_inspector_layout.addWidget(self.layout_name_input)

        if self._layout_editor is not None:
            self.layout_record_btn = RecordButton(self._layout_editor.recorder)
            self._layout_editor.recorder.key_recorded.connect(
                self._on_integrated_key_recorded
            )
        else:
            self.layout_record_btn = QPushButton("Record")
            self.layout_record_btn.setEnabled(False)
        layout_inspector_layout.addWidget(self.layout_record_btn)

        self.layout_delete_btn = QPushButton("Delete key")
        self.layout_delete_btn.clicked.connect(self._delete_layout_key)
        self.layout_delete_btn.setEnabled(False)
        layout_inspector_layout.addWidget(self.layout_delete_btn)

        layout_actions = QHBoxLayout()
        self.layout_add_btn = QPushButton("Add key")
        self.layout_add_btn.clicked.connect(self._add_layout_key)
        layout_actions.addWidget(self.layout_add_btn)
        self.layout_load_btn = QPushButton("Load layout")
        self.layout_load_btn.clicked.connect(self._choose_layout)
        layout_actions.addWidget(self.layout_load_btn)
        layout_inspector_layout.addLayout(layout_actions)
        layout_inspector_layout.addStretch()
        layout_inspector_layout.addWidget(
            QLabel("Drag: move key\nCtrl + drag: snap to grid\nScroll: zoom")
        )
        self.inspector_stack.addWidget(self.layout_inspector)

        self._overlay.hide()
        self._source_splitter_sizes = [260, 390]
        self._source_preview_visible = True
        self._settings = QSettings("KeydMapper", "KeydMapper")
        preview_visible = self._settings.value(
            "configEditor/showGeneratedConfig", True, type=bool
        )
        self._set_source_preview_visible(preview_visible, persist=False)

        if self._has_live_source:
            initial_source = self.source_editor.toPlainText()
            self._history = [initial_source]
            self._history_index = 0
            self._saved_source = initial_source
        self._refresh_layer_widgets(self._current_layer)
        self._update_history_actions()
        self._update_overall_status()
        if self._has_live_source:
            self._run_keyd_validation()

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
        """Enter physical-layout editing from the persistent left navigation."""
        if checked:
            self.enter_layout_mode()
        elif self._editing_layout:
            # Toggling the navigation item off mirrors Save layout and Done.
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
        """Add a physical key through the integrated controller."""
        if self._layout_editor is not None:
            self._layout_editor.add_key()

    def _delete_layout_key(self) -> None:
        """Delete selected physical keys through the integrated controller."""
        if self._layout_editor is not None:
            self._layout_editor.delete_selected_keys()

    def _choose_layout(self) -> None:
        """Open the saved-layout chooser without leaving the workspace."""
        if self._layout_editor is not None:
            self._layout_editor.choose_layout()

    def attach_view(self) -> None:
        """Attach the shared keyboard view between layer rail and inspector."""
        if self._splitter.indexOf(self._view) != -1:
            return
        self._splitter.insertWidget(1, self._view)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 5)
        self._splitter.setStretchFactor(2, 3)
        self._splitter.setSizes([180, 760, 430])

    def _on_layer_list_changed(self, layer: str) -> None:
        """Make the left rail the primary layer navigation control."""
        if not layer:
            return
        self.layer_combo.blockSignals(True)
        self.layer_combo.setCurrentText(layer)
        self.layer_combo.blockSignals(False)
        self._on_layer_changed(layer)

    def _refresh_layer_widgets(self, current_layer: str) -> None:
        """Synchronize the layer rail and compatibility combobox from the model."""
        if current_layer not in self.config.layers:
            current_layer = "main"

        self.layer_combo.blockSignals(True)
        self.layer_combo.clear()
        self.layer_combo.addItems(self.config.layer_order)
        self.layer_combo.setCurrentText(current_layer)
        self.layer_combo.blockSignals(False)

        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        self.layer_list.addItems(self.config.layer_order)
        matching_items = self.layer_list.findItems(
            current_layer, Qt.MatchFlag.MatchExactly
        )
        if matching_items:
            self.layer_list.setCurrentItem(matching_items[0])
        self.layer_list.blockSignals(False)
        self._current_layer = current_layer
        self.delete_layer_btn.setEnabled(current_layer != "main")

    def _create_new_layer(self) -> None:
        """Create a navigable layer without changing the selected key binding."""
        name, accepted = QInputDialog.getText(self, "New Layer", "Layer name:")
        if not accepted or not name.strip():
            return

        name = name.strip()
        if ":" in name:
            base, modifier = name.split(":", 1)
            modifier = modifier.strip().upper()
            name = (
                f"{base.strip()}:{modifier[0]}"
                if modifier and modifier[0] in {"C", "A", "M", "S", "G"}
                else base.strip()
            )

        if name not in self.config.layers:
            if self._has_live_source:
                self.config.add_layer(name)
            else:
                self.config.layers[name] = {}
                self.config.layer_order.append(name)
        self._current_layer = name
        self.on_config_structure_changed()
        self._on_layer_changed(name)

    def _set_source_editing(self, editing: bool) -> None:
        """Toggle explicit manual editing of the generated config."""
        self.source_editor.setReadOnly(not editing)
        self.edit_source_btn.setText("Done editing" if editing else "Edit config")
        if editing:
            self.source_editor.setFocus()
        else:
            self._commit_source_history()

    def _toggle_source_preview(self) -> None:
        self._set_source_preview_visible(not self._source_preview_visible)

    def _set_source_preview_visible(
        self, visible: bool, *, persist: bool = True
    ) -> None:
        """Collapse to the header and restore the user's previous split on show."""
        if not visible and self.expand_source_btn.isChecked():
            self.expand_source_btn.setChecked(False)

        current_sizes = self.inspector_splitter.sizes()
        if (
            not visible
            and self._source_preview_visible
            and len(current_sizes) == 2
            and current_sizes[1] > self.source_header_widget.sizeHint().height()
        ):
            self._source_splitter_sizes = current_sizes

        self._source_preview_visible = visible
        collapsed_height = (
            self.source_header_widget.sizeHint().height()
            + self.config_panel.layout().contentsMargins().top()
            + self.config_panel.layout().contentsMargins().bottom()
        )

        self.config_panel.setMaximumHeight(16777215 if visible else collapsed_height)
        self.source_editor.setVisible(visible)
        self.source_status.setVisible(visible)
        self.edit_source_btn.setVisible(visible)
        self.expand_source_btn.setVisible(visible)
        self.toggle_source_btn.setText("Hide" if visible else "Show")

        if visible:
            self.inspector_splitter.setSizes(self._source_splitter_sizes)
        else:
            total_height = max(sum(current_sizes), collapsed_height + 1)
            self.inspector_splitter.setSizes(
                [total_height - collapsed_height, collapsed_height]
            )

        if persist:
            self._settings.setValue("configEditor/showGeneratedConfig", visible)

    def _set_source_expanded(self, expanded: bool) -> None:
        """Temporarily give the generated config the whole inspector height."""
        if expanded and not self._source_preview_visible:
            self._set_source_preview_visible(True)
        if expanded:
            current_sizes = self.inspector_splitter.sizes()
            if len(current_sizes) == 2 and all(size > 0 for size in current_sizes):
                self._source_splitter_sizes = current_sizes
        self.actions_page.setVisible(not expanded)
        self.expand_source_btn.setText("Restore" if expanded else "Expand")
        if not expanded:
            self.inspector_splitter.setSizes(self._source_splitter_sizes)

    def _on_action_mode_changed(self, index: int) -> None:
        """Handles switching between different action modes."""
        self._action_stack.setCurrentIndex(index)
        self._on_selection_changed()

    def _on_layer_changed(self, layer: str) -> None:
        """Updates the editor when the active layer is changed."""
        if not layer:
            return
        self._current_layer = layer
        if hasattr(self, "layer_list"):
            matching_items = self.layer_list.findItems(
                layer, Qt.MatchFlag.MatchExactly
            )
            if matching_items and self.layer_list.currentItem() != matching_items[0]:
                self.layer_list.blockSignals(True)
                self.layer_list.setCurrentItem(matching_items[0])
                self.layer_list.blockSignals(False)
        self._refresh_scene_values()

        self.set_value_action.on_layer_changed(layer)
        self.change_layer_action.on_layer_changed(layer)

        if hasattr(self, "delete_layer_btn"):
            self.delete_layer_btn.setEnabled(layer != "main")

        self._on_selection_changed()
        self._focus_source_location(layer)

    def update_layer_name_in_combo(self, old_name: str, new_name: str) -> None:
        """Updates the main editor's UI to reflect a renamed layer."""
        if self._current_layer == old_name:
            self._current_layer = new_name
        self._refresh_layer_widgets(self._current_layer)

    def _delete_current_layer(self) -> None:
        """Deletes the currently selected layer."""
        if self._current_layer == "main":
            return

        confirm = QMessageBox.question(
            self,
            "Delete Layer",
            f"Are you sure you want to delete the layer '{self._current_layer}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        layer_to_delete = self._current_layer

        if layer_to_delete in self.config.layers:
            if self._has_live_source:
                self.config.delete_layer(layer_to_delete)
            else:
                del self.config.layers[layer_to_delete]
                if layer_to_delete in self.config.layer_order:
                    self.config.layer_order.remove(layer_to_delete)

        self._refresh_layer_widgets("main")
        self._on_layer_changed("main")
        self.on_config_structure_changed()

    def _refresh_scene_values(self) -> None:
        """Refreshes the displayed key values based on the current layer."""
        for item in self._scene.items():
            if isinstance(item, KeyItem):
                layer_dict = self.config.layers.get(self._current_layer, {})
                item.key_value = layer_dict.get(item.key_name, "")
                item.update()

    def set_key_mapping(self, key: KeyItem, val: str) -> None:
        """Updates the key mapping in both the visual scene and the configuration model."""
        key.key_value = val
        key.update()

        if self._has_live_source:
            self.config.set_mapping(
                self._current_layer,
                key.key_name,
                val,
            )
        else:
            if val:
                self.config.layers[self._current_layer][key.key_name] = val
            else:
                self.config.layers[self._current_layer].pop(key.key_name, None)
        self._sync_source_editor(focus_key=key.key_name)

    def on_config_structure_changed(self) -> None:
        """Refresh live source and completions after adding or renaming layers."""
        self._refresh_layer_widgets(self._current_layer)
        self._sync_source_editor()
        self.source_editor.set_completion_layers(self.config.layer_order)

    def _sync_source_editor(self, focus_key: str | None = None) -> None:
        """Show visual-model changes in source without moving the user's cursor."""
        if not self._has_live_source:
            return

        text = self.config.source()
        if self.source_editor.toPlainText() == text:
            self._update_source_status()
            self._update_overall_status()
            return

        cursor = self.source_editor.textCursor()
        cursor_position = cursor.position()
        scroll_position = self.source_editor.verticalScrollBar().value()
        self.source_editor.blockSignals(True)
        self.source_editor.setPlainText(text)
        self.source_editor.blockSignals(False)
        cursor = self.source_editor.textCursor()
        cursor.setPosition(min(cursor_position, len(text)))
        self.source_editor.setTextCursor(cursor)
        self.source_editor.verticalScrollBar().setValue(scroll_position)
        self._record_history(text)
        self._update_source_status()
        self._update_overall_status()
        if focus_key and self.source_editor.isReadOnly():
            self._focus_source_location(self._current_layer, focus_key)

    def _on_source_text_changed(self) -> None:
        """Queue source edits for debounced keyd validation and visual sync."""
        if not self._has_live_source or self._history_guard:
            return

        text = self.source_editor.toPlainText()
        self._pending_source_text = text
        self._history_timer.start()
        self._update_overall_status()
        diagnostics = Config.diagnostics(text)
        if diagnostics:
            self._update_source_status()
            return

        self._update_source_status()

    def _apply_source_to_visual_model(self, text: str) -> None:
        """Apply a keyd-validated manual source edit to visual controls."""
        current_layer = self._current_layer
        self.config.update_from_text(text)
        if current_layer not in self.config.layers:
            current_layer = "main"

        self._refresh_layer_widgets(current_layer)
        self.source_editor.set_completion_layers(self.config.layer_order)
        self.set_value_action.on_layer_changed(current_layer)
        self.change_layer_action.on_layer_changed(current_layer)
        self.delete_layer_btn.setEnabled(current_layer != "main")
        self._refresh_scene_values()
        self._on_selection_changed()

    def _update_source_status(self) -> None:
        """Display only config syntax state; save/apply state belongs in the toolbar."""
        diagnostics = Config.diagnostics(self.source_editor.toPlainText())
        if diagnostics:
            self._validation_timer.stop()
            self.source_status.setText(f"⚠ {diagnostics[0]}")
            self.source_status.setStyleSheet("color: #e5a50a;")
            self.save_apply_btn.setEnabled(False)
        else:
            self.source_status.setText("Checking keyd syntax…")
            self.source_status.setStyleSheet("")
            self.save_apply_btn.setEnabled(False)
            self._validation_timer.start()

    def _run_keyd_validation(self) -> None:
        """Run keyd's real parser after the user pauses typing."""
        text = self.source_editor.toPlainText()
        diagnostics = Config.diagnostics(text)
        if diagnostics:
            self._update_source_status()
            return

        valid, message = Config.check_source_text(text)
        if valid is True:
            self.source_status.setText("✓ keyd syntax valid")
            self.source_status.setStyleSheet("color: #57c75f;")
            self.save_apply_btn.setEnabled(True)
        elif valid is False:
            self.source_status.setText(f"⚠ {message}")
            self.source_status.setStyleSheet("color: #e5a50a;")
            self.save_apply_btn.setEnabled(False)
        else:
            self.source_status.setText(message)
            self.source_status.setStyleSheet("")
            self.save_apply_btn.setEnabled(True)

        if (
            valid is not False
            and self._pending_source_text is not None
            and self._pending_source_text == text
        ):
            self._apply_source_to_visual_model(text)
            self._pending_source_text = None

    def _update_overall_status(self) -> None:
        """Show document save state in the top command bar."""
        if not self._has_live_source:
            self.overall_status.clear()
            return
        modified = self.source_editor.toPlainText() != self._saved_source
        self.overall_status.setText("Unsaved changes" if modified else "Saved")
        self.overall_status.setStyleSheet(
            "color: #e5a50a;" if modified else "color: #57c75f;"
        )

    def _record_history(self, text: str) -> None:
        """Add a semantic config snapshot to the shared undo history."""
        if self._history_guard:
            return
        if self._history_index >= 0 and self._history[self._history_index] == text:
            return
        del self._history[self._history_index + 1 :]
        self._history.append(text)
        if len(self._history) > 100:
            self._history.pop(0)
        self._history_index = len(self._history) - 1
        self._update_history_actions()

    def _commit_source_history(self) -> None:
        """Group adjacent source keystrokes into one undo step."""
        if self._has_live_source:
            self._record_history(self.source_editor.toPlainText())

    def _update_history_actions(self) -> None:
        self.undo_btn.setEnabled(self._history_index > 0)
        self.redo_btn.setEnabled(
            0 <= self._history_index < len(self._history) - 1
        )

    def undo_config_change(self) -> None:
        """Undo the latest visual or source configuration change."""
        self._commit_source_history()
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._restore_history_snapshot()

    def redo_config_change(self) -> None:
        """Redo the next shared configuration change."""
        if self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._restore_history_snapshot()

    def _restore_history_snapshot(self) -> None:
        """Restore source and visual state from the selected history item."""
        text = self._history[self._history_index]
        self._history_guard = True
        self.source_editor.blockSignals(True)
        self.source_editor.setPlainText(text)
        self.source_editor.blockSignals(False)
        source_valid = False
        if not Config.diagnostics(text):
            valid, _ = Config.check_source_text(text)
            source_valid = valid is not False
        if source_valid:
            self.config.update_from_text(text)
            self._refresh_layer_widgets(self._current_layer)
            self._refresh_scene_values()
            self.source_editor.set_completion_layers(self.config.layer_order)
            self.set_value_action.on_layer_changed(self._current_layer)
            self.change_layer_action.on_layer_changed(self._current_layer)
            self._on_selection_changed()
        self._pending_source_text = None
        self._history_guard = False
        self._update_source_status()
        self._update_overall_status()
        self._update_history_actions()

    def _focus_source_location(
        self, layer: str, key: str | None = None
    ) -> None:
        """Reveal a binding in a layer, falling back to the layer declaration."""
        current_section: str | None = None
        layer_line = -1
        target_line = -1
        for line_number, line in enumerate(
            self.source_editor.toPlainText().splitlines()
        ):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]
                if current_section == layer:
                    layer_line = line_number
            elif key and current_section == layer and "=" in stripped:
                binding_key = stripped.split("=", 1)[0].strip()
                if binding_key == key:
                    target_line = line_number
        if target_line < 0:
            target_line = layer_line
        if target_line < 0:
            return

        cursor = QTextCursor(
            self.source_editor.document().findBlockByNumber(target_line)
        )
        if key and target_line != layer_line:
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        self.source_editor.setTextCursor(cursor)
        if key is None:
            self.source_editor.scroll_line_to_top(target_line)
        else:
            self.source_editor.ensureCursorVisible()

    @property
    def _active_action(self) -> ConfigActionWidget:
        """Returns the currently active action widget from the stack."""
        return cast(ConfigActionWidget, self._action_stack.currentWidget())

    def _on_selection_changed(self) -> None:
        """Handles selection changes by updating the active action widget."""
        super()._on_selection_changed()
        self._overlay.hide()
        if self._editing_layout:
            self._update_layout_selection()
            return
        key = self.get_selected_key_item()
        self.selection_hint.setText(
            f"Selected key: {key.key_name}" if key else "Select a key on the keyboard"
        )
        self._action_selector.setEnabled(key is not None)
        self._action_stack.setEnabled(key is not None)
        self._active_action.on_selection_changed(key)
        if key:
            self._focus_source_location(self._current_layer, key.key_name)

    def _save(self) -> None:
        """Saves the current configuration to disk."""
        if self._editing_layout:
            if self._layout_editor is not None:
                self._layout_editor.save_current_layout()
            self._leave_layout_mode()
            return

        diagnostics = Config.diagnostics(self.source_editor.toPlainText())
        if diagnostics:
            QMessageBox.warning(
                self,
                "Invalid configuration",
                f"Cannot save: {diagnostics[0]}",
            )
            return
        valid, message = Config.check_source_text(self.source_editor.toPlainText())
        if valid is False:
            QMessageBox.warning(
                self,
                "Invalid configuration",
                f"Cannot save: {message}",
            )
            return
        if self._pending_source_text == self.source_editor.toPlainText():
            self._apply_source_to_visual_model(self._pending_source_text)
            self._pending_source_text = None
        try:
            self.config.save()
            self._saved_source = self.source_editor.toPlainText()
            self._update_overall_status()
            self.cancel_requested.emit()
        except ConfigSaveError as e:
            QMessageBox.critical(self, "Error", str(e))

    def set_config_enabled(self) -> None:
        """Toggles the configuration's enabled state by calling the backend model function."""
        target_state = not self.config.name.endswith(".conf")

        try:
            self.config.set_config_enable(target_state)

            self.config_name_label.setText(f"{self.config.name}")
            self._update_enable_button()
            self._saved_source = self.source_editor.toPlainText()
            self._update_overall_status()
        except ConfigSaveError as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")

    def _update_enable_button(self) -> None:
        """Updates the enable/disable button based on the configuration name."""
        if self.config.name.endswith(".conf"):
            self.enable_btn.setText("Disable Config")
            self.enable_btn.setStyleSheet(
                """background-color: #d32f2f;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                """
            )
        else:
            self.enable_btn.setText("Enable Config")
            self.enable_btn.setStyleSheet(
                """background-color: #2e7d32;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                """
            )
