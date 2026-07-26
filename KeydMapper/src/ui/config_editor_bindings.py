"""Binding inspector and layer navigation for :mod:`ui.config_editor`."""

from typing import cast

from keyd.actions import ACTION_SPECS, ActionCategory
from keyd.config import ConfigSaveError
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from ui.actions.base import ConfigActionWidget
from ui.actions.keyd_action import KeydActionEditor
from ui.actions.set_value import SetValueAction
from ui.key_item import KeyItem

# This feature mixin is composed into ConfigEditor and shares its editor shell.
# pylint: disable=no-member,too-many-instance-attributes

LITERAL_BINDING = "literal"


class ConfigBindingsMixin:
    """Build and coordinate layer navigation and visual key bindings."""

    def _build_config_toolbar(self) -> None:
        """Build document-level commands in the editor's top bar."""
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._handle_back)
        self.toolbar_layout.addWidget(self.back_btn)

        self.config_name_label = QLabel(self.config.name)
        self.config_name_label.setStyleSheet(
            "font-weight: bold; margin-right: 5px;"
        )
        self.toolbar_layout.addWidget(self.config_name_label)

        self.enable_btn = QPushButton()
        self.enable_btn.clicked.connect(self.set_config_enabled)
        self.toolbar_layout.addWidget(self.enable_btn)
        self._update_enable_button()

        self.toolbar_layout.addSpacing(20)
        self.toolbar_layout.addStretch()

        # Compatibility adapter used internally by action widgets.
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

        self.cancel_btn.hide()
        self.save_btn.hide()

    def _build_layer_panel(self) -> None:
        """Build the resizable left navigation rail."""
        self.layer_panel = QFrame()
        self.layer_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.layer_panel.setMinimumWidth(0)
        self.layer_panel.setMaximumWidth(16777215)
        layout = QVBoxLayout(self.layer_panel)
        layout.addWidget(QLabel("LAYERS"))

        self.layer_list = QListWidget()
        self.layer_list.addItems(self.config.layer_order)
        self.layer_list.currentTextChanged.connect(self._on_layer_list_changed)
        layout.addWidget(self.layer_list, stretch=1)

        layer_buttons = QHBoxLayout()
        self.new_layer_btn = QPushButton("+ Layer")
        self.new_layer_btn.clicked.connect(self._create_new_layer)
        layer_buttons.addWidget(self.new_layer_btn)

        self.delete_layer_btn = QPushButton("Delete")
        self.delete_layer_btn.clicked.connect(self._delete_current_layer)
        self.delete_layer_btn.setEnabled(False)
        layer_buttons.addWidget(self.delete_layer_btn)
        layout.addLayout(layer_buttons)

        self._build_layout_navigation(layout)
        self._splitter.insertWidget(0, self.layer_panel)
        self._splitter.setChildrenCollapsible(True)

    def _build_inspector_shell(self) -> None:
        """Create the right stack shared by Binding and Physical layout modes."""
        self.side_panel.setMinimumWidth(0)
        self.side_panel.setMaximumWidth(16777215)
        self.inspector_stack = QStackedWidget()
        self.panel_layout.addWidget(self.inspector_stack)

        self.inspector_splitter = QSplitter(Qt.Orientation.Vertical)
        self.inspector_splitter.setChildrenCollapsible(True)
        self.inspector_stack.addWidget(self.inspector_splitter)

    def _build_binding_panel(self) -> None:
        """Build controls for the currently selected visual key binding."""
        self.actions_page = QWidget()
        layout = QVBoxLayout(self.actions_page)
        layout.setContentsMargins(6, 6, 6, 6)
        title = QLabel("BINDING")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)
        self.selection_hint = QLabel("Select a key on the keyboard")
        self.selection_hint.setWordWrap(True)
        layout.addWidget(self.selection_hint)
        layout.addWidget(QLabel("Action:"))

        self._action_selector = QComboBox()
        self._populate_action_selector()
        layout.addWidget(self._action_selector)

        self._action_stack = QStackedWidget()
        self.set_value_action = SetValueAction(self)
        self.keyd_action = KeydActionEditor(self)
        self._action_stack.addWidget(self.set_value_action)
        self._action_stack.addWidget(self.keyd_action)
        self._action_selector.currentIndexChanged.connect(
            self._on_action_selected
        )
        layout.addWidget(self._action_stack)
        layout.addStretch()
        self.inspector_splitter.addWidget(self.actions_page)

    def _populate_action_selector(self) -> None:
        """Add literal input first, followed by labelled action groups."""
        self._action_selector.addItem("Key / shortcut", LITERAL_BINDING)
        model = cast(QStandardItemModel, self._action_selector.model())

        for category in ActionCategory:
            self._action_selector.insertSeparator(
                self._action_selector.count()
            )
            header_index = self._action_selector.count()
            self._action_selector.addItem(category.value)
            header = model.item(header_index)
            header.setEnabled(False)
            font = header.font()
            font.setBold(True)
            header.setFont(font)

            for spec in ACTION_SPECS:
                if spec.category is category:
                    self._action_selector.addItem(
                        spec.label,
                        spec.keyd_function,
                    )

    def attach_view(self) -> None:
        """Place the shared keyboard view between navigation and inspector."""
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
        """Synchronize the layer rail and compatibility combo from the model."""
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
        """Create a navigable layer without changing the selected binding."""
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

    def _on_action_selected(self, index: int) -> None:
        """Open the literal editor or selected structured action form."""
        action_name = self._action_selector.itemData(index)
        if not action_name:
            return
        if action_name == LITERAL_BINDING:
            self._action_stack.setCurrentIndex(0)
            self._active_action.on_selection_changed(
                self.get_selected_key_item()
            )
        else:
            self._action_stack.setCurrentIndex(1)
            self.keyd_action.select_action(str(action_name))

    def _on_layer_changed(self, layer: str) -> None:
        """Update the keyboard and inspectors for the active layer."""
        if not layer:
            return
        self._current_layer = layer
        matching_items = self.layer_list.findItems(
            layer, Qt.MatchFlag.MatchExactly
        )
        if matching_items and self.layer_list.currentItem() != matching_items[0]:
            self.layer_list.blockSignals(True)
            self.layer_list.setCurrentItem(matching_items[0])
            self.layer_list.blockSignals(False)
        self._refresh_scene_values()

        self.set_value_action.on_layer_changed(layer)
        self.keyd_action.on_layer_changed(layer)
        self.delete_layer_btn.setEnabled(layer != "main")
        self._on_selection_changed()
        self._focus_source_location(layer)

    def update_layer_name_in_combo(self, old_name: str, new_name: str) -> None:
        """Refresh navigation after a layer rename."""
        if self._current_layer == old_name:
            self._current_layer = new_name
        self._refresh_layer_widgets(self._current_layer)

    def _delete_current_layer(self) -> None:
        """Delete the current non-main layer after confirmation."""
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
        """Refresh displayed key values from the active layer."""
        layer = self.config.layers.get(self._current_layer, {})
        for item in self._scene.items():
            if isinstance(item, KeyItem):
                item.key_value = layer.get(item.key_name, "")
                item.update()

    def set_key_mapping(self, key: KeyItem, val: str) -> None:
        """Update a key in both the visual scene and configuration model."""
        key.key_value = val
        key.update()
        if self._has_live_source:
            self.config.set_mapping(self._current_layer, key.key_name, val)
        elif val:
            self.config.layers[self._current_layer][key.key_name] = val
        else:
            self.config.layers[self._current_layer].pop(key.key_name, None)
        self._sync_source_editor(focus_key=key.key_name)

    def on_config_structure_changed(self) -> None:
        """Refresh navigation, source and completions after structural edits."""
        self._refresh_layer_widgets(self._current_layer)
        self._sync_source_editor()
        self.source_editor.set_completion_layers(self.config.layer_order)

    @property
    def _active_action(self) -> ConfigActionWidget:
        """Return the visible binding action widget."""
        return cast(ConfigActionWidget, self._action_stack.currentWidget())

    def set_config_enabled(self) -> None:
        """Toggle the configuration's enabled filename suffix."""
        target_state = not self.config.name.endswith(".conf")
        try:
            self.config.set_config_enable(target_state)
            self.config_name_label.setText(self.config.name)
            self._update_enable_button()
            self._saved_source = self.source_editor.toPlainText()
            self._update_overall_status()
        except ConfigSaveError as error:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save configuration: {error}",
            )

    def _update_enable_button(self) -> None:
        """Reflect the configuration's enabled state."""
        if self.config.name.endswith(".conf"):
            text = "Disable Config"
            colour = "#d32f2f"
        else:
            text = "Enable Config"
            colour = "#2e7d32"
        self.enable_btn.setText(text)
        self.enable_btn.setStyleSheet(
            f"""background-color: {colour};
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: bold;
            """
        )
