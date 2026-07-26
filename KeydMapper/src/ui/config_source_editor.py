"""Source editor widgets for keyd configuration files."""

from __future__ import annotations

import re

# Qt helper widgets intentionally expose their behaviour through framework hooks.
# pylint: disable=too-few-public-methods

from keyd.key_validator import get_valid_keys
from PySide6.QtCore import QRect, QSize, Qt, QStringListModel
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


KEYD_ACTIONS = (
    "layer()",
    "oneshot()",
    "swap()",
    "setlayout()",
    "clear()",
    "toggle()",
    "layerm()",
    "oneshotm()",
    "oneshotk()",
    "swapm()",
    "togglem()",
    "clearm()",
    "repeat()",
    "overload()",
    "overloadt()",
    "overloadt2()",
    "overloadi()",
    "lettermod()",
    "timeout()",
    "macro()",
    "macro2()",
    "command()",
    "noop",
)

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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
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

    def keyPressEvent(self, event: QKeyEvent) -> None:  # pylint: disable=invalid-name
        """Handle indentation and display context-sensitive completions."""
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
