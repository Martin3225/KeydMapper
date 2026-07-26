"""Action widget for mapping keys to layer switches."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QVBoxLayout,
)
from ui.actions.base import ConfigActionWidget
from ui.key_item import KeyItem

if TYPE_CHECKING:
    from ui.config_editor import ConfigEditor


class ChangeLayerAction(ConfigActionWidget):
    """Action to map a key to a layer change ('layer(layer_name)')."""

    def __init__(self, editor: "ConfigEditor"):
        super().__init__(editor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(QLabel("Select target layer:"))
        self._layer_selector = QComboBox()
        self._layer_selector.currentTextChanged.connect(self._on_layer_selected)
        layout.addWidget(self._layer_selector)

        # Modifiers row for the layer definition
        modifiers = {"C": "Ctrl", "S": "Shift", "A": "Alt", "M": "Meta", "G": "AltGr"}
        mod_layout = QHBoxLayout()
        mod_layout.setContentsMargins(0, 5, 0, 0)
        self._mod_checkboxes: dict[str, QCheckBox] = {}
        for mod, label in modifiers.items():
            cb = QCheckBox(label)
            cb.setToolTip(
                f"""{mod} modifier for this layer.
(Note: A layer can have only 1 modifier).

Warning: In keyd, layer modifiers only apply to unmapped keys!
If you remap a key inside this layer, the {mod} modifier will be disabled when you pressed it.
For example, if you want 'tab' to act as '{mod}-tab', you MUST explicitly map it to '{mod}-tab'."""
            )
            cb.stateChanged.connect(self._on_modifier_toggled)
            self._mod_checkboxes[mod] = cb
            mod_layout.addWidget(cb)
        layout.addLayout(mod_layout)

        self.on_layer_changed("")

    def on_layer_changed(self, layer: str) -> None:
        """Update the list of available layers."""
        _ = layer  # Unused, but required by signal signature
        self._layer_selector.blockSignals(True)
        self._layer_selector.clear()
        self._layer_selector.addItems(self.editor.config.layer_order)
        self._layer_selector.addItem("+ New layer")
        self._layer_selector.blockSignals(False)
        self._update_selection()

    def on_selection_changed(self, key_item: KeyItem | None) -> None:
        """Updates the UI when the selected key changes."""
        _ = key_item
        self._update_selection()

    def _update_selection(self) -> None:
        """Synchronizes the layer selector with the currently selected key's value."""
        key = self.editor.get_selected_key_item()
        if not key:
            self._layer_selector.setEnabled(False)
            self._layer_selector.setCurrentIndex(-1)
            return

        self._layer_selector.setEnabled(True)

        # Check if the value matches a layer-related command
        val = key.key_value
        found = False
        for i in range(self._layer_selector.count()):
            layer_name = self._layer_selector.itemText(i)
            base_layer = layer_name.split(":")[0]
            if val == f"layer({base_layer})":
                self._layer_selector.setCurrentIndex(i)
                self._update_checkboxes_from_layer(layer_name)
                found = True
                break

        if not found:
            self._layer_selector.setCurrentIndex(-1)
            self._update_checkboxes_from_layer("")

    def _on_layer_selected(self, text: str) -> None:
        """Handles user selection of a layer from the dropdown."""
        if text == "+ New layer":
            self._create_new_layer()
            return

        self._update_checkboxes_from_layer(text)

        key = self.editor.get_selected_key_item()
        if not key:
            return

        self._apply_layer_mapping(key, text)

    def _create_new_layer(self) -> None:
        """Prompts the user for a new layer name, validates it, and creates it."""
        name, ok = QInputDialog.getText(self, "New Layer", "Layer name:")

        if not (ok and name):
            self._update_selection()

        name = name.strip()
        if ":" in name:
            parts = name.split(":")
            base = parts[0].strip()
            mod = parts[1].strip()

            valid_mods = {"C", "A", "M", "S", "G"}
            if mod and mod[0].upper() in valid_mods:
                name = f"{base}:{mod[0].upper()}"
            else:
                name = base

        if name not in self.editor.config.layers:
            self.editor.config.layers[name] = {}
            self.editor.config.layer_order.append(name)
            self.editor.layer_combo.addItem(name)
            self.on_layer_changed("")
            self._layer_selector.setCurrentText(name)
        else:
            self._layer_selector.setCurrentText(name)

    def _apply_layer_mapping(self, key: KeyItem, layer_name: str) -> None:
        """Applies the layer mapping to the given key."""
        base_layer = layer_name.split(":")[0]
        val = f"layer({base_layer})"
        self.editor.set_key_mapping(key, val)

    def _update_checkboxes_from_layer(self, layer_name: str) -> None:
        """Updates the checkboxes based on the layer modifiers."""
        if not layer_name:
            for cb in self._mod_checkboxes.values():
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
                cb.setEnabled(False)
            return

        for cb in self._mod_checkboxes.values():
            cb.setEnabled(True)

        active_mod = layer_name.split(":")[1] if ":" in layer_name else None

        for mod, cb in self._mod_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(mod == active_mod)
            cb.blockSignals(False)

    def _on_modifier_toggled(self) -> None:
        """Updates the layer definition when a modifier is toggled."""
        # Ensure only one modifier can be active
        sender = self.sender()
        if isinstance(sender, QCheckBox) and sender.isChecked():
            for cb in self._mod_checkboxes.values():
                if cb != sender:
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)

        current_layer_name = self._layer_selector.currentText()
        if not current_layer_name:
            return

        base_layer = current_layer_name.split(":")[0]
        active_mod = next(
            (mod for mod, cb in self._mod_checkboxes.items() if cb.isChecked()), None
        )
        new_layer_name = f"{base_layer}:{active_mod}" if active_mod else base_layer

        if new_layer_name == current_layer_name:
            return

        self._rename_layer(current_layer_name, new_layer_name)

    def _rename_layer(self, old_name: str, new_name: str) -> None:
        """Renames a layer in the config and updates the UI comboboxes."""
        config = self.editor.config
        if old_name in config.layers:
            config.layers[new_name] = config.layers.pop(old_name)

        if old_name in config.layer_order:
            idx = config.layer_order.index(old_name)
            config.layer_order[idx] = new_name

        self.on_layer_changed("")

        self.editor.update_layer_name_in_combo(old_name, new_name)
