"""Integrated visual editor for keyd bindings and physical layouts."""

from typing import TYPE_CHECKING

from keyd.actions import parse_action
from keyd.config import Config, ConfigSaveError
from PySide6.QtWidgets import QGraphicsScene, QMessageBox
from ui.base_editor import BaseEditor
from ui.config_editor_bindings import LITERAL_BINDING, ConfigBindingsMixin
from ui.config_editor_history import ConfigHistoryMixin
from ui.config_editor_layout import PhysicalLayoutMixin
from ui.config_editor_source import ConfigSourceMixin
from ui.context import EditorContext
from ui.key_item import KeyItem
from ui.layout_view import LayoutView

if TYPE_CHECKING:
    from ui.layout_editor import LayoutEditor


# The feature mixins own their widgets; the orchestrator intentionally exposes
# those controls for the existing UI tests and action-widget adapters.
# pylint: disable=too-many-ancestors
class ConfigEditor(
    PhysicalLayoutMixin,
    ConfigHistoryMixin,
    ConfigSourceMixin,
    ConfigBindingsMixin,
    BaseEditor,
):
    """Coordinate the binding, source and physical-layout editor features."""

    _pending_source_text: str | None
    _saved_source: str

    def __init__(
        self,
        config: Config,
        scene: QGraphicsScene,
        view: LayoutView,
        layout_editor: "LayoutEditor | None" = None,
    ):
        super().__init__(context=EditorContext(scene=scene, view=view))
        self.config = config
        self._layout_editor = layout_editor
        self._editing_layout = False
        self._current_layer = "main"

        self._setup_source_state()
        self.save_requested.connect(self._save)

        self._build_config_toolbar()
        self._build_layer_panel()
        self._build_inspector_shell()
        self._build_binding_panel()
        self._build_source_panel()
        self._build_layout_inspector()

        self._overlay.hide()
        self._refresh_layer_widgets(self._current_layer)
        self._initialize_source_editor()

    def _on_selection_changed(self) -> None:
        """Route the scene selection to the active integrated editor."""
        super()._on_selection_changed()
        self._overlay.hide()
        if self._editing_layout:
            self._update_layout_selection()
            return

        key = self.get_selected_key_item()
        self.selection_hint.setText(
            f"Selected key: {key.key_name}"
            if key
            else "Select a key on the keyboard"
        )
        self._action_selector.setEnabled(key is not None)
        self._action_stack.setEnabled(key is not None)
        self._select_binding_editor_for(key)
        self._active_action.on_selection_changed(key)
        if key:
            self._focus_source_location(self._current_layer, key.key_name)

    def _select_binding_editor_for(self, key: KeyItem | None) -> None:
        """Choose structured actions for parsed keyd calls, literal input otherwise."""
        parsed = parse_action(key.key_value) if key else None
        action_name = parsed.action_name if parsed else LITERAL_BINDING
        desired_index = self._action_selector.findData(action_name)
        if self._action_selector.currentIndex() != desired_index:
            self._action_selector.blockSignals(True)
            self._action_selector.setCurrentIndex(desired_index)
            self._action_selector.blockSignals(False)
        self._action_stack.setCurrentIndex(1 if parsed else 0)

    def _save(self) -> None:
        """Save the active physical layout or validated keyd configuration."""
        if self._editing_layout:
            if self._layout_editor is not None:
                self._layout_editor.save_current_layout()
            self._leave_layout_mode()
            return

        source = self.source_editor.toPlainText()
        diagnostics = Config.diagnostics(source)
        if diagnostics:
            QMessageBox.warning(
                self,
                "Invalid configuration",
                f"Cannot save: {diagnostics[0]}",
            )
            return

        valid, message = Config.check_source_text(source)
        if valid is False:
            QMessageBox.warning(
                self,
                "Invalid configuration",
                f"Cannot save: {message}",
            )
            return
        if self._pending_source_text == source:
            self._apply_source_to_visual_model(source)
            self._pending_source_text = None

        try:
            self.config.save()
            self._saved_source = source
            self._update_overall_status()
            self.cancel_requested.emit()
        except ConfigSaveError as error:
            QMessageBox.critical(self, "Error", str(error))

    def shutdown(self) -> None:
        """Stop editor-owned capture and detach the shared scene safely."""
        self.set_value_action.shutdown()
        super().shutdown()
