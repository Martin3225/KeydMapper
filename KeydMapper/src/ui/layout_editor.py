"""Editor mode for designing the visual keyboard layout (positioning keys)."""



from keyd.key_recorder import KeyRecorder
from keyd.key_validator import is_valid_key
from keyd.layout import (
    Layout,
    LayoutButton,
    load_layout,
    load_layout_from_path,
    save_layout,
)
from PySide6.QtCore import QRectF, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsScene,
    QLabel,
    QLineEdit,
    QPushButton,
)
from ui.base_editor import BaseEditor
from ui.context import EditorContext
from ui.key_item import KEY_DEFAULT_HEIGHT, KEY_DEFAULT_WIDTH, KeyItem
from ui.layout_view import LayoutView
from ui.load_layout_dialog import LoadLayoutDialog
from ui.record_button import RecordButton


# @generated [partially] Gemini 3.1: Graphics and styling adjustments
# Number of attributes is high due to the UI layout
# pylint: disable=too-many-instance-attributes
class LayoutEditor(BaseEditor):
    """Editor mode for designing the visual keyboard layout (positioning keys)."""

    layout_done = Signal()

    # pylint: disable=too-many-positional-arguments
    def __init__(
        self,
        device_id: str,
        scene: QGraphicsScene,
        view: LayoutView,
    ):
        context = EditorContext(
            scene=scene, view=view
        )
        super().__init__(
            context=context,
        )
        self._device_id = device_id
        self.save_requested.connect(self._save)

        self._recorder = KeyRecorder(device_id, parent=self)
        self._recorder.key_recorded.connect(self._on_key_recorded)

        # Toolbar
        add_btn = QPushButton("Add button")
        add_btn.clicked.connect(self._add_button)
        self.toolbar_layout.addWidget(add_btn)

        load_btn = QPushButton("Load layout")
        load_btn.clicked.connect(self._load_layout_dialog)
        self.toolbar_layout.addWidget(load_btn)
        self.toolbar_layout.addStretch()

        # Side Panel
        self.panel_layout.addWidget(QLabel("Key:"))
        self._name_input = QLineEdit()
        self._name_input.textEdited.connect(self._apply_key)
        self.panel_layout.addWidget(self._name_input)

        self._delete_btn = QPushButton("Delete key")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_key)
        self.panel_layout.addWidget(self._delete_btn)

        self._record_btn = RecordButton(self._recorder)
        self.panel_layout.addWidget(self._record_btn)

        self.panel_layout.addStretch()
        self.panel_layout.addWidget(
            QLabel("Scroll: zoom\nCtrl + drag: snap to grid\nMiddle mouse: pan")
        )

        self._clipboard: list[tuple[float, float, float, float]] = []
        self._populate_scene(load_layout(device_id))

    def activate_mode(self) -> None:
        """Sets up the shared view and items for layout editing."""
        self._view.disconnect_signals()

        self._view.delete_requested.connect(self._delete_key)
        self._view.add_requested.connect(self._add_button)
        self._view.copy_requested.connect(self._copy_keys)
        self._view.paste_requested.connect(self._paste_keys)
        for item in self._scene.items():
            if isinstance(item, KeyItem):
                item.locked = False
                # In layout mode, we show the key name
                item.key_value = ""
                item.update()

    def _on_key_recorded(self, key_name: str) -> None:
        """Apply the next logical input emitted by the active keyd config."""
        self._name_input.setText(key_name)
        self._apply_key()

    def _populate_scene(self, layout: Layout) -> None:
        """Clears the scene and adds KeyItems from the provided layout."""
        self._scene.clear()
        for btn in layout.buttons:
            self._scene.addItem(
                KeyItem(
                    btn.name, btn.default, QRectF(btn.x, btn.y, btn.width, btn.height)
                )
            )

    def _add_button(self) -> None:
        """Adds a new default KeyItem to the center of the view."""
        center = self._view.mapToScene(self._view.viewport().rect().center())
        item = KeyItem(
            "Key",
            "",
            QRectF(
                center.x() - KEY_DEFAULT_WIDTH / 2,
                center.y() - KEY_DEFAULT_HEIGHT / 2,
                KEY_DEFAULT_WIDTH,
                KEY_DEFAULT_HEIGHT,
            ),
        )
        self._scene.addItem(item)
        item.update_overlap()
        self._scene.clearSelection()
        item.setSelected(True)

    def _load_layout_dialog(self) -> None:
        """Opens a dialog to load a layout from a file."""
        dialog = LoadLayoutDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_path:
            self._populate_scene(load_layout_from_path(dialog.selected_path))

    def _on_selection_changed(self) -> None:
        """Updates the side panel UI based on the currently selected key."""
        super()._on_selection_changed()
        key = self.get_selected_key_item()
        if key:
            self._name_input.setText(key.key_name)
            self._delete_btn.setEnabled(True)
            self._record_btn.setEnabled(True)
        else:
            self._name_input.clear()
            self._delete_btn.setEnabled(False)
            self._record_btn.setEnabled(False)
            self._record_btn.reset()

    # Qt framwork invalid methods names
    # pylint: disable=invalid-name
    def hideEvent(self, event) -> None:
        """Stops recording when the widget is hidden."""
        self._record_btn.reset()
        super().hideEvent(event)

    def _apply_key(self, _text: str = "") -> None:
        """Applies the current input name to the selected key."""
        error = self.rename_selected_key(self._name_input.text())
        if error == "invalid":
            self._name_input.setStyleSheet("border: 1px solid orange;")
        elif error == "duplicate":
            self._name_input.setStyleSheet("border: 1px solid red;")
        elif error is None:
            self._name_input.setStyleSheet("")

    def rename_selected_key(self, name: str) -> str | None:
        """Rename the selected key and return a compact validation error code."""
        key = self.get_selected_key_item()
        name = name.strip()
        if not key or not name:
            return "empty"
        if not is_valid_key(name):
            return "invalid"
        if any(
            isinstance(item, KeyItem) and item is not key and item.key_name == name
            for item in self._scene.items()
        ):
            return "duplicate"
        key.key_name = name
        key.update()
        return None

    @property
    def recorder(self) -> KeyRecorder:
        """Expose the shared recorder to the integrated layout inspector."""
        return self._recorder

    def add_key(self) -> None:
        """Add a key through the reusable layout controller."""
        self._add_button()

    def delete_selected_keys(self) -> None:
        """Delete selected keys through the reusable layout controller."""
        self._delete_key()

    def choose_layout(self) -> None:
        """Open the layout chooser through the reusable layout controller."""
        self._load_layout_dialog()

    def reload_saved_layout(self) -> None:
        """Discard in-memory geometry changes and restore the saved layout."""
        self._populate_scene(load_layout(self._device_id))

    def _delete_key(self) -> None:
        """Deletes all currently selected KeyItems from the scene."""
        for item in self._scene.selectedItems():
            if isinstance(item, KeyItem):
                self._scene.removeItem(item)

    def _copy_keys(self) -> None:
        """Copies the geometry of selected KeyItems to the clipboard."""
        selected = [i for i in self._scene.selectedItems() if isinstance(i, KeyItem)]
        if not selected:
            return
        centre_x = sum(i.pos().x() + i.rect.width() / 2 for i in selected) / len(
            selected
        )
        centre_y = sum(i.pos().y() + i.rect.height() / 2 for i in selected) / len(
            selected
        )
        self._clipboard = [
            (
                i.pos().x() - centre_x,
                i.pos().y() - centre_y,
                i.rect.width(),
                i.rect.height(),
            )
            for i in selected
        ]

    def _paste_keys(self) -> None:
        """Pastes KeyItems from the clipboard to the center of the view."""
        if not self._clipboard:
            return
        center = self._view.mapToScene(self._view.viewport().rect().center())
        self._scene.clearSelection()
        for rel_x, rel_y, w, h in self._clipboard:
            item = KeyItem(
                "Key", "Key", QRectF(center.x() + rel_x, center.y() + rel_y, w, h)
            )
            self._scene.addItem(item)
            item.update_overlap()
            item.setSelected(True)

    def _save(self) -> None:
        """Saves the current layout (positions and sizes) to disk."""
        self.save_current_layout()
        self.layout_done.emit()

    def save_current_layout(self) -> None:
        """Persist the current physical layout without changing editor mode."""
        buttons = [
            LayoutButton(
                name=item.key_name,
                default=item.key_value,
                x=item.pos().x(),
                y=item.pos().y(),
                width=item.rect.width(),
                height=item.rect.height(),
            )
            for item in self._scene.items()
            if isinstance(item, KeyItem)
        ]
        save_layout(Layout(device_id=self._device_id, buttons=buttons))

    def shutdown(self) -> None:
        """Stop input capture and detach the shared scene."""
        self._record_btn.reset()
        self._view.disconnect_signals()
        super().shutdown()
