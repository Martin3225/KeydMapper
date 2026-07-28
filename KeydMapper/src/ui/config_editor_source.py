"""Generated-config panel, validation and history for :mod:`ui.config_editor`."""

from keyd.config import Config
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from ui.config_source_editor import KeydSourceEditor

# This feature mixin is composed into ConfigEditor and therefore uses widgets
# and callbacks created by the other editor feature mixins.
# pylint: disable=no-member,too-many-instance-attributes,too-few-public-methods


class ConfigSourceMixin:
    """Own the live source preview, validation and shared undo history."""

    def _setup_source_state(self) -> None:
        """Create state and debounce timers before source widgets are built."""
        self._has_live_source = isinstance(
            getattr(self.config, "source_text", None), str
        )
        self._pending_source_text: str | None = None
        self._saved_source = ""
        self._source_model_refresh = False
        self._setup_history_state()

        self._validation_timer = QTimer(self)
        self._validation_timer.setSingleShot(True)
        self._validation_timer.setInterval(300)
        self._validation_timer.timeout.connect(self._run_keyd_validation)

    def _build_source_panel(self) -> None:
        """Build the generated-config half of the right inspector."""
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
        self.source_editor.setToolTip(
            "Editable live keyd configuration. Ctrl+Space: suggestions, "
            "Alt+Up/Down: move lines, Ctrl+S: format."
        )
        self.source_editor.format_requested.connect(self._format_source_editor)
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

    def _initialize_source_editor(self) -> None:
        """Restore preview preferences and establish the initial history item."""
        self._source_splitter_sizes = [260, 390]
        self._source_preview_visible = True
        self._settings = QSettings("KeydMapper", "KeydMapper")
        preview_visible = self._settings.value(
            "configEditor/showGeneratedConfig", True, type=bool
        )
        self._set_source_preview_visible(preview_visible, persist=False)

        if self._has_live_source:
            initial_source = self.source_editor.toPlainText()
            self._saved_source = initial_source
        else:
            initial_source = None
        self._initialize_history(initial_source)
        self._update_overall_status()
        if self._has_live_source:
            self._run_keyd_validation()

    def _format_source_editor(self) -> None:
        """Apply conservative structural formatting and preserve text selection."""
        source = self.source_editor.toPlainText()
        formatted = Config.format_source_structure(source)
        if formatted == source:
            return

        cursor = self.source_editor.textCursor()
        source_lines = source.split("\n")
        formatted_lines = formatted.split("\n")

        def position_marker(position: int) -> tuple[int | None, int, int]:
            line_number = source.count("\n", 0, position)
            line_start = source.rfind("\n", 0, position) + 1
            column = position - line_start
            if (
                line_number < len(source_lines)
                and source_lines[line_number].strip()
            ):
                ordinal = sum(
                    bool(line.strip())
                    for line in source_lines[:line_number]
                )
                return ordinal, line_number, column
            return None, line_number, column

        def marker_position(marker: tuple[int | None, int, int]) -> int:
            ordinal, old_line, column = marker
            target_line = min(old_line, max(0, len(formatted_lines) - 1))
            if ordinal is not None:
                nonblank_index = -1
                for index, line in enumerate(formatted_lines):
                    if line.strip():
                        nonblank_index += 1
                    if nonblank_index == ordinal:
                        target_line = index
                        break
            prefix_length = sum(
                len(line) + 1 for line in formatted_lines[:target_line]
            )
            return prefix_length + min(
                column,
                len(formatted_lines[target_line]),
            )

        anchor_marker = position_marker(cursor.anchor())
        position_marker_value = position_marker(cursor.position())
        scroll_position = self.source_editor.verticalScrollBar().value()
        self.source_editor.setPlainText(formatted)

        restored = self.source_editor.textCursor()
        restored.setPosition(marker_position(anchor_marker))
        restored.setPosition(
            marker_position(position_marker_value),
            QTextCursor.MoveMode.KeepAnchor,
        )
        self.source_editor.setTextCursor(restored)
        self.source_editor.verticalScrollBar().setValue(scroll_position)

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
        margins = self.config_panel.layout().contentsMargins()
        collapsed_height = (
            self.source_header_widget.sizeHint().height()
            + margins.top()
            + margins.bottom()
        )

        self.config_panel.setMaximumHeight(16777215 if visible else collapsed_height)
        self.source_editor.setVisible(visible)
        self.source_status.setVisible(visible)
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
        if focus_key:
            self._focus_source_location(self._current_layer, focus_key)

    def _on_source_text_changed(self) -> None:
        """Queue source edits for debounced keyd validation and visual sync."""
        if not self._has_live_source or self._history_guard:
            return

        text = self.source_editor.toPlainText()
        self._pending_source_text = text
        self._history_timer.start()
        self._update_overall_status()
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
        self.keyd_action.on_layer_changed(current_layer)
        self.delete_layer_btn.setEnabled(current_layer != "main")
        self._refresh_scene_values()
        self._source_model_refresh = True
        try:
            self._on_selection_changed()
        finally:
            self._source_model_refresh = False

    def _update_source_status(self) -> None:
        """Display syntax state; save/apply state belongs in the toolbar."""
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

    def _focus_source_location(
        self, layer: str, key: str | None = None
    ) -> None:
        """Reveal a binding in a layer, falling back to the layer declaration."""
        if self._source_model_refresh or self.source_editor.hasFocus():
            # Manual source editing owns the cursor. Validation may refresh
            # the visual model, but must not move or select source text.
            return
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
        if (
            self.source_editor.isReadOnly()
            and key
            and target_line != layer_line
        ):
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        self.source_editor.setTextCursor(cursor)
        if key is None:
            self.source_editor.scroll_line_to_top(target_line)
        else:
            self.source_editor.ensureCursorVisible()
