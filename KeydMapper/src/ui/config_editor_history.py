"""Shared source/visual undo history for :mod:`ui.config_editor`."""

from keyd.config import Config
from PySide6.QtCore import QTimer

# This feature mixin is composed into ConfigEditor and shares its editor shell.
# pylint: disable=no-member,too-many-instance-attributes


class ConfigHistoryMixin:
    """Store semantic source snapshots used by visual and textual changes."""

    def _setup_history_state(self) -> None:
        """Create the bounded history and its typing debounce timer."""
        self._history_guard = False
        self._history: list[str] = []
        self._history_index = -1
        self._history_timer = QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.setInterval(350)
        self._history_timer.timeout.connect(self._commit_source_history)

    def _initialize_history(self, initial_source: str | None) -> None:
        """Establish the initial document snapshot, when source is available."""
        if initial_source is not None:
            self._history = [initial_source]
            self._history_index = 0
        self._update_history_actions()

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
        """Enable only history directions that currently have a snapshot."""
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
            self.keyd_action.on_layer_changed(self._current_layer)
            self._on_selection_changed()

        self._pending_source_text = None
        self._history_guard = False
        self._update_source_status()
        self._update_overall_status()
        self._update_history_actions()
