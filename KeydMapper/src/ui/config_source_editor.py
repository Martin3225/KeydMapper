"""Source editor widgets for keyd configuration files."""

from __future__ import annotations

import re

# Qt helper widgets intentionally expose their behaviour through framework hooks.
# pylint: disable=too-few-public-methods

from keyd.actions import action_completions
from keyd.key_validator import get_valid_keys
from PySide6.QtCore import QRect, QSize, Qt, QStringListModel, Signal
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QKeyEvent,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget


KEYD_ACTIONS = action_completions()

KEYD_GLOBALS = (
    "macro_timeout",
    "macro_repeat_timeout",
    "macro_sequence_timeout",
    "layer_indicator",
    "chord_timeout",
    "chord_hold_timeout",
    "oneshot_timeout",
    "disable_modifier_guard",
    "overload_tap_timeout",
)


class KeydSyntaxHighlighter(QSyntaxHighlighter):
    """Small syntax highlighter tailored to keyd's INI-like grammar."""

    def __init__(self, document) -> None:
        super().__init__(document)
        self._comment = self._format("#7f8c8d", italic=True)
        self._section = self._format("#4ec9b0", bold=True)
        self._key = self._format("#9cdcfe")
        self._action = self._format("#dcdcaa", bold=True)
        self._modifier = self._format("#c586c0")
        self._number = self._format("#b5cea8")

    @staticmethod
    def _format(
        colour: str, *, bold: bool = False, italic: bool = False
    ) -> QTextCharFormat:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(colour))
        text_format.setFontWeight(700 if bold else 400)
        text_format.setFontItalic(italic)
        return text_format

    def highlightBlock(self, text: str) -> None:  # pylint: disable=invalid-name
        """Apply keyd syntax colours to one document block."""
        stripped = text.lstrip()
        if stripped.startswith("#"):
            start = len(text) - len(stripped)
            self.setFormat(start, len(text) - start, self._comment)
            return

        section = re.match(r"^\s*\[[^\]]+\]\s*$", text)
        if section:
            self.setFormat(section.start(), section.end(), self._section)
            return

        assignment = re.match(r"^(\s*)([^=]+?)(\s*=\s*)(.*)$", text)
        if not assignment:
            return

        self.setFormat(
            assignment.start(2),
            assignment.end(2) - assignment.start(2),
            self._key,
        )
        value = assignment.group(4)
        value_start = assignment.start(4)
        for match in re.finditer(r"\b[a-z][a-z0-9_]*(?=\()", value):
            self.setFormat(
                value_start + match.start(),
                match.end() - match.start(),
                self._action,
            )
        for match in re.finditer(r"\b(?:C|M|A|S|G)(?=-)", value):
            self.setFormat(
                value_start + match.start(),
                match.end() - match.start(),
                self._modifier,
            )
        for match in re.finditer(r"\b\d+(?:ms)?\b", value):
            self.setFormat(
                value_start + match.start(),
                match.end() - match.start(),
                self._number,
            )


class LineNumberArea(QWidget):
    """Gutter owned by :class:`KeydSourceEditor`."""

    def __init__(self, editor: "KeydSourceEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Size the gutter to the editor's current line-number width."""
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Delegate gutter painting to the editor."""
        self._editor.paint_line_number_area(event)


class KeydSourceEditor(QPlainTextEdit):
    """Code editor with line numbers, highlighting and context completion."""

    format_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        # Allow navigation targets near EOF to be aligned with the viewport top.
        self.setCenterOnScroll(True)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setStyleSheet(
            "QPlainTextEdit { background: #1e1e1e; color: #d4d4d4;"
            " selection-background-color: #264f78; }"
        )

        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_line_number_area_width()
        self._highlight_current_line()

        self._completion_model = QStringListModel(self)
        self.completer = QCompleter(self._completion_model, self)
        self.completer.setWidget(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.activated.connect(self._insert_completion)
        self.set_completion_layers([])

        self.highlighter = KeydSyntaxHighlighter(self.document())

    def set_completion_layers(self, layers: list[str]) -> None:
        """Refresh completions that depend on the live configuration."""
        sections = ["[ids]", "[global]", "[aliases]", "[main]"]
        sections.extend(f"[{layer}]" for layer in layers if layer != "main")
        layer_actions = []
        for layer in layers:
            base_layer = layer.split(":", 1)[0]
            layer_actions.extend(
                (
                    f"layer({base_layer})",
                    f"oneshot({base_layer})",
                    f"toggle({base_layer})",
                    f"setlayout({base_layer})",
                )
            )
        words = sorted(
            set(
                sections
                + list(KEYD_ACTIONS)
                + list(KEYD_GLOBALS)
                + ["include"]
                + layer_actions
                + list(get_valid_keys())
            ),
            key=str.casefold,
        )
        self._completion_model.setStringList(words)

    def line_number_area_width(self) -> int:
        """Return gutter width for the current number of blocks."""
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def scroll_line_to_top(self, line_number: int) -> None:
        """Align a document line with the top edge of the code viewport."""
        self.verticalScrollBar().setValue(max(0, line_number))

    def _update_line_number_area_width(self, _count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, delta_y: int) -> None:
        if delta_y:
            self._line_number_area.scroll(0, delta_y)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Keep the line-number gutter aligned with the viewport."""
        super().resizeEvent(event)
        contents = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(
                contents.left(),
                contents.top(),
                self.line_number_area_width(),
                contents.height(),
            )
        )

    def paint_line_number_area(self, event) -> None:
        """Paint visible line numbers in the gutter."""
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#252526"))
        painter.setPen(QColor("#858585"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    int(Qt.AlignmentFlag.AlignRight),
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self) -> None:
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#2a2d2e"))
        selection.format.setProperty(
            QTextFormat.Property.FullWidthSelection, True
        )
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def _completion_prefix(self) -> str:
        cursor = self.textCursor()
        before_cursor = cursor.block().text()[: cursor.positionInBlock()]
        match = re.search(r"(?:\[[A-Za-z0-9_+:-]*|[A-Za-z0-9_+:-]+)$", before_cursor)
        return match.group(0) if match else ""

    def _insert_completion(self, completion: str) -> None:
        prefix = self._completion_prefix()
        cursor = self.textCursor()
        if prefix:
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.KeepAnchor,
                len(prefix),
            )
        cursor.insertText(completion)
        if completion.endswith("()"):
            cursor.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(cursor)

    def _move_selected_lines(self, direction: int) -> None:
        """Move the current line or selected line block one position."""
        text = self.toPlainText()
        lines = text.split("\n")
        cursor = self.textCursor()
        document = self.document()

        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        start_block = document.findBlock(selection_start)
        end_block = document.findBlock(selection_end)
        start_line = start_block.blockNumber()
        end_line = end_block.blockNumber()
        if (
            selection_end > selection_start
            and end_block.position() == selection_end
        ):
            end_line -= 1

        last_line = len(lines) - 1
        if lines and lines[-1] == "":
            last_line -= 1
        if (
            direction < 0
            and start_line <= 0
            or direction > 0
            and end_line >= last_line
        ):
            return

        cursor_line = cursor.blockNumber()
        cursor_column = cursor.positionInBlock()
        anchor_block = document.findBlock(cursor.anchor())
        anchor_line = anchor_block.blockNumber()
        anchor_column = cursor.anchor() - anchor_block.position()

        def moved_line(line_number: int) -> int:
            if direction < 0:
                if start_line <= line_number <= end_line:
                    return line_number - 1
                if line_number == start_line - 1:
                    return end_line
            else:
                if start_line <= line_number <= end_line:
                    return line_number + 1
                if line_number == end_line + 1:
                    return start_line
            return line_number

        if direction < 0:
            lines[start_line - 1 : end_line + 1] = (
                lines[start_line : end_line + 1]
                + [lines[start_line - 1]]
            )
        else:
            lines[start_line : end_line + 2] = (
                [lines[end_line + 1]]
                + lines[start_line : end_line + 1]
            )

        scroll_position = self.verticalScrollBar().value()
        self.setPlainText("\n".join(lines))

        def document_position(line_number: int, column: int) -> int:
            block = self.document().findBlockByNumber(line_number)
            return block.position() + min(column, len(block.text()))

        restored = self.textCursor()
        restored.setPosition(
            document_position(moved_line(anchor_line), anchor_column)
        )
        restored.setPosition(
            document_position(moved_line(cursor_line), cursor_column),
            QTextCursor.MoveMode.KeepAnchor,
        )
        self.setTextCursor(restored)
        self.verticalScrollBar().setValue(scroll_position)

    def _handle_command_shortcut(self, event: QKeyEvent) -> bool:
        """Handle editor commands before ordinary text input."""
        modifiers = event.modifiers()
        key = event.key()
        control = Qt.KeyboardModifier.ControlModifier
        control_shift = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
        )
        handled = True

        if modifiers == control and key == Qt.Key.Key_Z:
            self.undo_requested.emit()
        elif modifiers == control_shift and key == Qt.Key.Key_Z:
            self.redo_requested.emit()
        elif (
            modifiers == Qt.KeyboardModifier.AltModifier
            and key in (Qt.Key.Key_Up, Qt.Key.Key_Down)
        ):
            self._move_selected_lines(-1 if key == Qt.Key.Key_Up else 1)
        elif modifiers == control_shift and key == Qt.Key.Key_F:
            self.format_requested.emit()
        else:
            handled = False

        if handled:
            self.completer.popup().hide()
        return handled

    def keyPressEvent(self, event: QKeyEvent) -> None:  # pylint: disable=invalid-name
        """Handle indentation and display context-sensitive completions."""
        if self.isReadOnly():
            self.completer.popup().hide()
            super().keyPressEvent(event)
            return

        if self._handle_command_shortcut(event):
            return

        popup = self.completer.popup()
        if popup.isVisible() and event.key() in (
            Qt.Key.Key_Enter,
            Qt.Key.Key_Return,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        ):
            event.ignore()
            return

        completion_shortcut = (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Space
        )
        if not completion_shortcut:
            if event.key() == Qt.Key.Key_Tab:
                self.insertPlainText("    ")
                return
            super().keyPressEvent(event)

        prefix = self._completion_prefix()
        typed_character = event.text()
        should_complete = completion_shortcut or (
            len(prefix) >= 1
            and typed_character
            and (
                typed_character[-1].isalnum()
                or typed_character[-1] in "_[:-"
            )
        )
        if not should_complete:
            popup.hide()
            return

        self.completer.setCompletionPrefix(prefix)
        popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
        completion_rect = self.cursorRect()
        completion_rect.setWidth(
            popup.sizeHintForColumn(0)
            + popup.verticalScrollBar().sizeHint().width()
        )
        self.completer.complete(completion_rect)

    def focusOutEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Request formatting when the user actually leaves the editor."""
        super().focusOutEvent(event)
        if event.reason() != Qt.FocusReason.PopupFocusReason:
            self.format_requested.emit()
