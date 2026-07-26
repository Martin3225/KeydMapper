"""Editor for keyd configuration."""

from typing import cast

from keyd.config import Config, ConfigSaveError
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsScene,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
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
    ):
        context = EditorContext(scene=scene, view=view)
        super().__init__(
            context=context,
        )
        self.config = config
        self._has_live_source = isinstance(
            getattr(self.config, "source_text", None), str
        )
        self.save_requested.connect(self._save)
        self._current_layer = "main"

        # Toolbar
        self.config_name_label = QLabel(f"{self.config.name}")
        self.config_name_label.setStyleSheet("font-weight: bold; margin-right: 5px;")
        self.toolbar_layout.addWidget(self.config_name_label)

        self.enable_btn = QPushButton()
        self.enable_btn.clicked.connect(self.set_config_enabled)
        self.toolbar_layout.addWidget(self.enable_btn)
        self._update_enable_button()

        self.toolbar_layout.addSpacing(20)

        self.toolbar_layout.addWidget(QLabel("Layer:"))
        self.layer_combo = QComboBox()
        self.layer_combo.addItems(self.config.layer_order)
        self.layer_combo.currentTextChanged.connect(self._on_layer_changed)
        self.toolbar_layout.addWidget(self.layer_combo)

        self.delete_layer_btn = QPushButton("Delete layer")
        self.delete_layer_btn.clicked.connect(self._delete_current_layer)
        self.toolbar_layout.addWidget(self.delete_layer_btn)
        if self._current_layer == "main":
            self.delete_layer_btn.setEnabled(False)

        self.toolbar_layout.addStretch()

        # Side panel tabs: visual actions and the lossless live config source.
        self.side_panel.setMinimumWidth(380)
        self.panel_tabs = QTabWidget()
        self.panel_layout.addWidget(self.panel_tabs)

        self.actions_page = QWidget()
        actions_layout = QVBoxLayout(self.actions_page)
        actions_layout.setContentsMargins(6, 6, 6, 6)
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
        actions_layout.addWidget(QLabel("Scroll: zoom\nMiddle mouse: pan"))

        self.source_page = QWidget()
        source_layout = QVBoxLayout(self.source_page)
        source_layout.setContentsMargins(6, 6, 6, 6)

        self.source_status = QLabel()
        self.source_status.setWordWrap(True)
        source_layout.addWidget(self.source_status)

        self.source_editor = KeydSourceEditor()
        self.source_editor.setToolTip(
            "Live keyd configuration source. Press Ctrl+Space for suggestions."
        )
        if self._has_live_source:
            self.source_editor.setPlainText(self.config.source())
            self.source_editor.set_completion_layers(self.config.layer_order)
            self._update_source_status()
        self.source_editor.textChanged.connect(self._on_source_text_changed)
        source_layout.addWidget(self.source_editor, stretch=1)

        self.panel_tabs.addTab(self.actions_page, "Actions")
        self.panel_tabs.addTab(self.source_page, "Config source")
        self.panel_tabs.currentChanged.connect(self._on_panel_tab_changed)

        # Keep the selection overlay on the action page so source is always usable.
        self._overlay.setParent(self.actions_page)
        self.actions_page.installEventFilter(self)

    def activate_mode(self) -> None:
        """Sets up the shared view and items for configuration editing."""
        self._view.disconnect_signals()

        for item in self._scene.items():
            if isinstance(item, KeyItem):
                item.locked = True
        self._refresh_scene_values()
        self._sync_source_editor()

    def eventFilter(self, obj, event) -> bool:
        """Keep the action-only selection overlay fitted to its tab."""
        if (
            hasattr(self, "actions_page")
            and obj == self.actions_page
            and event.type() == event.Type.Resize
        ):
            self._overlay.resize(event.size())
        return super().eventFilter(obj, event)

    def _on_panel_tab_changed(self, index: int) -> None:
        """Only show the key-selection overlay on the visual actions tab."""
        if index == self.panel_tabs.indexOf(self.source_page):
            self._overlay.hide()
        else:
            self._on_selection_changed()

    def _on_action_mode_changed(self, index: int) -> None:
        """Handles switching between different action modes."""
        self._action_stack.setCurrentIndex(index)
        self._on_selection_changed()

    def _on_layer_changed(self, layer: str) -> None:
        """Updates the editor when the active layer is changed."""
        if not layer:
            return
        self._current_layer = layer
        self._refresh_scene_values()

        self.set_value_action.on_layer_changed(layer)
        self.change_layer_action.on_layer_changed(layer)

        if hasattr(self, "delete_layer_btn"):
            self.delete_layer_btn.setEnabled(layer != "main")

        self._on_selection_changed()

    def update_layer_name_in_combo(self, old_name: str, new_name: str) -> None:
        """Updates the main editor's UI to reflect a renamed layer."""
        self.layer_combo.blockSignals(True)
        main_idx = self.layer_combo.findText(old_name)
        if main_idx >= 0:
            self.layer_combo.setItemText(main_idx, new_name)
        self.layer_combo.blockSignals(False)

        if self._current_layer == old_name:
            self._current_layer = new_name

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

        self.layer_combo.blockSignals(True)
        self.layer_combo.removeItem(self.layer_combo.findText(layer_to_delete))
        self.layer_combo.blockSignals(False)

        self.layer_combo.setCurrentText("main")
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
        self._sync_source_editor()

    def on_config_structure_changed(self) -> None:
        """Refresh live source and completions after adding or renaming layers."""
        self._sync_source_editor()
        self.source_editor.set_completion_layers(self.config.layer_order)

    def _sync_source_editor(self) -> None:
        """Show visual-model changes in source without moving the user's cursor."""
        if not self._has_live_source:
            return

        text = self.config.source()
        if self.source_editor.toPlainText() == text:
            self._update_source_status()
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
        self._update_source_status()

    def _on_source_text_changed(self) -> None:
        """Apply source edits to the visual model immediately."""
        if not self._has_live_source:
            return

        current_layer = self._current_layer
        self.config.update_from_text(self.source_editor.toPlainText())
        if current_layer not in self.config.layers:
            current_layer = "main"

        self.layer_combo.blockSignals(True)
        self.layer_combo.clear()
        self.layer_combo.addItems(self.config.layer_order)
        self.layer_combo.setCurrentText(current_layer)
        self.layer_combo.blockSignals(False)
        self._current_layer = current_layer

        self.source_editor.set_completion_layers(self.config.layer_order)
        self.set_value_action.on_layer_changed(current_layer)
        self.change_layer_action.on_layer_changed(current_layer)
        self.delete_layer_btn.setEnabled(current_layer != "main")
        self._refresh_scene_values()
        self._on_selection_changed()
        self._update_source_status()

    def _update_source_status(self) -> None:
        """Display lightweight live feedback; keyd performs final validation on save."""
        diagnostics = Config.diagnostics(self.source_editor.toPlainText())
        if diagnostics:
            self.source_status.setText(f"⚠ {diagnostics[0]}")
            self.source_status.setStyleSheet("color: #e5a50a;")
        else:
            self.source_status.setText("● Live — visual editor synchronized")
            self.source_status.setStyleSheet("color: #57c75f;")

    @property
    def _active_action(self) -> ConfigActionWidget:
        """Returns the currently active action widget from the stack."""
        return cast(ConfigActionWidget, self._action_stack.currentWidget())

    def _on_selection_changed(self) -> None:
        """Handles selection changes by updating the active action widget."""
        super()._on_selection_changed()
        if (
            hasattr(self, "panel_tabs")
            and self.panel_tabs.currentWidget() == self.source_page
        ):
            self._overlay.hide()
        key = self.get_selected_key_item()
        self._active_action.on_selection_changed(key)

    def _save(self) -> None:
        """Saves the current configuration to disk."""
        try:
            self.config.save()
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
