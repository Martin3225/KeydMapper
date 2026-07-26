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
)
from ui.actions.base import ConfigActionWidget
from ui.actions.change_layer import ChangeLayerAction
from ui.actions.set_value import SetValueAction
from ui.base_editor import BaseEditor
from ui.context import EditorContext
from ui.key_item import KeyItem
from ui.layout_view import LayoutView


# @generated [partially] Gemini 3.1: Graphics and styling adjustments
# Number of attributes is high due to the UI layout
# pylint: disable=too-many-instance-attributes
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

        # Side Panel - Action Selector
        self.panel_layout.addWidget(QLabel("Action:"))
        self._action_selector = QComboBox()
        self._action_selector.addItems(["Set key value", "Change layer"])
        self._action_selector.currentIndexChanged.connect(self._on_action_mode_changed)
        self.panel_layout.addWidget(self._action_selector)

        # Side Panel - Action Stack
        self._action_stack = QStackedWidget()
        self.set_value_action = SetValueAction(self)
        self.change_layer_action = ChangeLayerAction(self)

        self._action_stack.addWidget(self.set_value_action)
        self._action_stack.addWidget(self.change_layer_action)
        self.panel_layout.addWidget(self._action_stack)

        self.panel_layout.addStretch()
        self.panel_layout.addWidget(QLabel("Scroll: zoom\nMiddle mouse: pan"))

    def activate_mode(self) -> None:
        """Sets up the shared view and items for configuration editing."""
        self._view.disconnect_signals()

        for item in self._scene.items():
            if isinstance(item, KeyItem):
                item.locked = True
        self._refresh_scene_values()

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
            del self.config.layers[layer_to_delete]
        if layer_to_delete in self.config.layer_order:
            self.config.layer_order.remove(layer_to_delete)

        self.layer_combo.blockSignals(True)
        self.layer_combo.removeItem(self.layer_combo.findText(layer_to_delete))
        self.layer_combo.blockSignals(False)

        self.layer_combo.setCurrentText("main")

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

        if val:
            self.config.layers[self._current_layer][key.key_name] = val
        else:
            self.config.layers[self._current_layer].pop(key.key_name, None)

    @property
    def _active_action(self) -> ConfigActionWidget:
        """Returns the currently active action widget from the stack."""
        return cast(ConfigActionWidget, self._action_stack.currentWidget())

    def _on_selection_changed(self) -> None:
        """Handles selection changes by updating the active action widget."""
        super()._on_selection_changed()
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
